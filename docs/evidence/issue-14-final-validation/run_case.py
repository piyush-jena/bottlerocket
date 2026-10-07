"""Boot one R10.2 image, prove its policy and execute the requested container test."""
import base64
import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

BASE = Path(__file__).resolve().parent
CASE = json.loads(Path(sys.argv[1]).read_text())
OUT = BASE / "cases" / (CASE["variant"] + "-" + CASE["arch"])
OUT.mkdir(parents=True, exist_ok=True)
assert not (OUT / "launch-started.json").exists(), "Reconcile existing launch before retrying"
inputs = OUT / "test-inputs"
inputs.mkdir(exist_ok=True)
input_hashes = {}
for name in ["policy.py", "run_case.py", "transport.py"]:
    data = (BASE / name).read_bytes()
    (inputs / name).write_bytes(data)
    input_hashes[name] = hashlib.sha256(data).hexdigest()
(inputs / "sha256.json").write_text(json.dumps(input_hashes, indent=2) + "\n")
REGION = "us-west-2"

def save(name, value):
    (OUT / (name + ".json")).write_text(json.dumps(value, indent=2) + "\n")

def aws(label, *args):
    response = subprocess.run(["aws", *args, "--region", REGION, "--output", "json"],
        capture_output=True, text=True, timeout=60,
        env=os.environ | {"AWS_PAGER": "", "AWS_MAX_ATTEMPTS": "1"})
    (OUT / (label + ".stdout")).write_text(response.stdout)
    (OUT / (label + ".stderr")).write_text(response.stderr)
    assert response.returncode == 0, (label, response.stderr)
    return json.loads(response.stdout or "{}")

try:
    identity = aws("identity", "sts", "get-caller-identity")
    assert identity["Account"] == "533267423195"
    config = json.loads((BASE / "release-config.json").read_text())
    assert CASE["source"] == config["source"]
    image = aws("image", "ec2", "describe-images", "--image-ids", CASE["ami"])["Images"][0]
    assert image["State"] == "available" and not image["Public"] and image["OwnerId"] == identity["Account"]
    assert "symphony.14.r10" in image["Name"]
    assert image["Architecture"] == ("arm64" if CASE["arch"] == "aarch64" else "x86_64")
    assert {x["Key"]: x["Value"] for x in image["Tags"]}["SymphonyBuild"] == CASE["job"]
    network = json.loads((BASE / "network.json").read_text())
    stack = json.loads((BASE / "stack-observed.json").read_text())["Stacks"][0]
    assert stack["StackStatus"] == "CREATE_COMPLETE"
    outputs = {x["OutputKey"]: x["OutputValue"] for x in stack["Outputs"]}
    nvidia_variant = "-nvidia" in CASE["variant"]
    nvidia = nvidia_variant and not network.get("non_gpu_fallback", False)
    instance_type = network.get("gpu_instance_type", "g6.xlarge") if nvidia else ("m6g.large" if CASE["arch"] == "aarch64" else "m6i.large")
    userdata = (BASE / "userdata.toml").read_text()
    tags = [{"Key": "Name", "Value": "symphony.14.r10-" + CASE["variant"]},
        {"Key": "SymphonyIssue", "Value": "14"}, {"Key": "SymphonyBuild", "Value": CASE["job"]}]
    launch = {"ImageId": CASE["ami"], "InstanceType": instance_type, "MinCount": 1, "MaxCount": 1,
        "ClientToken": "symphony-14-r10-" + CASE["job"] + ("-" + instance_type if nvidia else ""), "IamInstanceProfile": {"Name": outputs["Profile"]},
        "NetworkInterfaces": [{"DeviceIndex": 0, "SubnetId": network["subnet"], "Groups": [outputs["SecurityGroup"]],
            "AssociatePublicIpAddress": True, "DeleteOnTermination": True}],
        "UserData": userdata, "MetadataOptions": {"HttpTokens": "required", "HttpPutResponseHopLimit": 2},
        "TagSpecifications": [{"ResourceType": kind, "Tags": tags} for kind in ["instance", "volume"]]}
    save("launch-input", launch)
    save("launch-started", {"at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "case": CASE})
    launched = aws("launch", "ec2", "run-instances", "--cli-input-json", json.dumps(launch))
    assert len(launched["Instances"]) == 1
    instance = launched["Instances"][0]["InstanceId"]
    save("identity", {"instance": instance, "instance_type": instance_type, **CASE})
    received = aws("userdata", "ec2", "describe-instance-attribute", "--instance-id", instance, "--attribute", "userData")
    assert base64.b64decode(received["UserData"]["Value"]).decode() == userdata
    print(instance, CASE["variant"], "launched", flush=True)
    deadline = time.monotonic() + 900
    while True:
        status = aws("ssm-status", "ssm", "describe-instance-information", "--filters", "Key=InstanceIds,Values=" + instance)
        rows = status["InstanceInformationList"]
        if rows and rows[0]["PingStatus"] == "Online":
            break
        assert time.monotonic() < deadline, "SSM did not become Online"
        time.sleep(15)
    os.environ["R10_INSTANCE"] = instance
    os.environ["R10_COMMAND_LOG"] = str(OUT / "commands")
    from transport import admin, deliver, host, ssm

    def policy(label):
        source = base64.b64encode(gzip.compress((inputs / "policy.py").read_bytes())).decode()
        remote = "/.bottlerocket/rootfs/local/symphony-14-runtime/policy-" + uuid.uuid4().hex
        code = f"""import base64,contextlib,gzip,io,json,pathlib,sys
sys.argv=['policy.py',{config['build_id']!r}]
buffer=io.StringIO()
try:
 with contextlib.redirect_stdout(buffer):
  exec(gzip.decompress(base64.b64decode({source!r})))
except SystemExit:
 pass
p=pathlib.Path({remote!r});p.parent.mkdir(parents=True,exist_ok=True)
packed=gzip.compress(buffer.getvalue().encode());p.write_bytes(packed)
print(json.dumps({{'path':str(p),'size':len(packed)}}))
"""
        receipt = json.loads(ssm(label, admin(code), 300))
        packed = bytearray()
        for offset in range(0, receipt["size"], 6000):
            read = ("import base64,pathlib;p=pathlib.Path(" + repr(receipt["path"]) + ");"
                + f"print(base64.b64encode(p.read_bytes()[{offset}:{offset+6000}]).decode())")
            packed.extend(base64.b64decode(ssm(label + "-read", admin(read)).strip()))
        assert len(packed) == receipt["size"]
        raw = gzip.decompress(packed)
        report = json.loads(raw)
        save(label, report)
        assert report["status"] == "passed", report["errors"]
        return report

    deadline = time.monotonic() + 600
    while True:
        output = ssm("admin-readiness", "if apiclient exec admin true >/dev/null 2>&1; then echo ADMIN_READY; else echo ADMIN_WAIT; fi")
        if output.strip() == "ADMIN_READY":
            break
        assert output.strip() == "ADMIN_WAIT" and time.monotonic() < deadline
        time.sleep(10)
    before = policy("policy-before")
    print(instance, "boot and R10.2 policy passed", flush=True)
    pins = json.loads((BASE / "image-pins.json").read_text())
    def checked(label, *argv, timeout=180):
        rc, stdout, stderr = host(label, list(argv), timeout)
        assert rc == 0, (label, stderr)
        return stdout
    existing = checked("container-preflight", "ctr", "-n", "default", "containers", "list", "-q")
    assert not any(name in existing.splitlines() for name in ["nvspec", "nvidia-smoke1", "symphony14-native-spec", "symphony14-native-smoke"])
    checked("rootfs-preflight", "test", "!", "-e", "/local/nvidia-rootfs" if nvidia else "/local/symphony14-native-rootfs")
    if nvidia:
        with (OUT / "nvidia-smoke.stdout").open("w") as stdout, (OUT / "nvidia-smoke.stderr").open("w") as stderr:
            result = subprocess.run([str(BASE / "nvidia-smoke-test/run-nvidia-smoke.sh"),
                instance, REGION, pins["nvidia"]["image"]], stdout=stdout, stderr=stderr, timeout=2400)
        output = (OUT / "nvidia-smoke.stdout").read_text()
        assert result.returncode == 0, "NVIDIA smoke script failed"
        assert "Result = PASS" in output and "Test PASSED" in output and "NVIDIA" in output and "NumDevs = 1" in output, "CUDA success output missing"
        smoke = {"kind": "nvidia", "image": pins["nvidia"]["image"], "exit_code": result.returncode,
            "device_query": "PASS", "vector_add": "PASSED"}
    else:
        image_ref = pins["native"]["image"]
        rootfs = "/local/symphony14-native-rootfs"
        checked("native-pull", "ctr", "-n", "default", "images", "pull", image_ref, timeout=900)
        checked("native-mkdir", "mkdir", "-p", rootfs)
        checked("native-mount", "ctr", "-n", "default", "images", "mount", "--rw", image_ref, rootfs)
        checked("native-label", "chcon", "-R", "system_u:object_r:data_t:s0", rootfs)
        checked("native-helper", "ctr", "-n", "default", "container", "create", image_ref, "symphony14-native-spec")
        info = json.loads(checked("native-info", "ctr", "-n", "default", "container", "info", "symphony14-native-spec"))
        spec = info["Spec"]
        spec["root"] = {"path": rootfs, "readonly": False}
        spec["process"]["args"] = ["sh", "-c", "echo R10_NATIVE_CONTAINER_PASS; uname -m"]
        spec["process"]["selinuxLabel"] = "system_u:system_r:container_t:s0"
        spec.setdefault("linux", {})["mountLabel"] = "system_u:object_r:data_t:s0"
        (OUT / "native-spec.json").write_text(json.dumps(spec))
        deliver(OUT / "native-spec.json", "/local/symphony14-native-spec.json")
        output = checked("native-run", "ctr", "-n", "default", "run", "--rm", "--rootfs",
            "-c", "/local/symphony14-native-spec.json", "symphony14-native-smoke")
        assert "R10_NATIVE_CONTAINER_PASS" in output and CASE["arch"] in output
        (OUT / "native-smoke.stdout").write_text(output)
        checked("native-clean-helper", "ctr", "-n", "default", "container", "rm", "symphony14-native-spec")
        checked("native-clean-mount", "ctr", "-n", "default", "images", "unmount", rootfs)
        rc, _, stderr = host("native-clean-snapshot", ["ctr", "-n", "default", "snapshots", "rm", rootfs])
        assert rc == 0 or "not found" in stderr.lower(), stderr
        smoke = {"kind": "native", "image": image_ref, "exit_code": 0, "output": output.strip()}
    if nvidia_variant and not nvidia:
        smoke["gpu_smoke"] = "not run: operator authorized ordinary-instance validation after GPU capacity refusal"
    after = policy("policy-after")
    assert before["boot_id"] == after["boot_id"]
    save("result", {"status": "passed", "case": CASE, "instance": instance, "smoke": smoke,
        "boot_id": before["boot_id"], "finished_at": datetime.datetime.now(datetime.timezone.utc).isoformat()})
    print(instance, "boot, policy and container checks passed", flush=True)
except Exception as error:
    save("result", {"status": "failed", "case": CASE, "instance": globals().get("instance"), "error": repr(error)})
    if "instance" in globals():
        try:
            console = aws("failure-console", "ec2", "get-console-output", "--instance-id", instance, "--latest")
            output = console.get("Output", "")
            try:
                output = base64.b64decode(output, validate=True).decode(errors="replace")
            except Exception:
                pass
            (OUT / "failure-console.txt").write_text(output)
        except Exception as capture_error:
            (OUT / "console-error.txt").write_text(repr(capture_error))
    raise
