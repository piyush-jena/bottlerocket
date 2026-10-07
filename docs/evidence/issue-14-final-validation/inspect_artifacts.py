"""Read existing NVIDIA disk images using the already-present SDK; no compilation."""
import concurrent.futures,datetime,hashlib,json,subprocess,re,shutil
from pathlib import Path
BASE=Path(__file__).resolve().parent
SDK="public.ecr.aws/bottlerocket/bottlerocket-sdk:v0.79.0"
def run(argv):
 r=subprocess.run(argv,capture_output=True,text=True)
 return {"argv":argv,"returncode":r.returncode,"stdout":r.stdout,"stderr":r.stderr}
def inspect(p):
 d=json.loads(p.read_text());image=Path(next(i["image"] for i in d["images"] if not i["image"].endswith("-data.img")))
 commands=[]
 part=run(["sfdisk","--json",str(image)]);commands.append(part);assert part["returncode"]==0
 table=json.loads(part["stdout"])["partitiontable"]
 root=next(x for x in table["partitions"] if x.get("name")=="BOTTLEROCKET-ROOT-A")["start"]*table["sectorsize"]
 efi=next(x for x in table["partitions"] if x.get("name")=="EFI-SYSTEM")["start"]*table["sectorsize"]
 prefix=["docker","run","--rm","--network","none","--read-only","--tmpfs","/tmp","-v",str(image.parent)+":/input:ro","--entrypoint","/bin/bash",SDK]
 # Preserve lookup failures. dump.erofs requires physical paths through /usr symlinks.
 previous=p.parent/"static-inspection.json"
 if previous.exists():shutil.copy2(previous,p.parent/"static-inspection-offset-attempt.json")
 superblock=run(prefix+["-c",'dump.erofs --offset="$2" -s "$1"',"inspect","/input/"+image.name,str(root)])
 commands.append(superblock);assert superblock["returncode"]==0
 blocks=int(re.search(r'Filesystem blocks:\s+(\d+)',superblock["stdout"])[1])
 blocksize=int(re.search(r'Filesystem blocksize:\s+(\d+)',superblock["stdout"])[1])
 partition=p.parent/"root-partition.img"
 with image.open("rb") as src,partition.open("wb") as dst:
  src.seek(root); remaining=blocks*blocksize
  while remaining:
   chunk=src.read(min(remaining,8*1024*1024));assert chunk;dst.write(chunk);remaining-=len(chunk)
 checks={}
 for path in ["/x86_64-bottlerocket-linux-gnu/sys-root/usr/lib/systemd/system","/x86_64-bottlerocket-linux-gnu/sys-root/usr/lib/systemd/system/sysinit.target.wants","/x86_64-bottlerocket-linux-gnu/sys-root/usr/lib/modules"]:
  receipt=run(prefix+["-c",'dump.erofs --ls --path="$2" "$1"',"inspect","/input/root-partition.img",path]);commands.append(receipt)
  assert receipt["returncode"]==0 and not receipt["stderr"],receipt
  if "systemd" in path:assert "proc-sys-fs-binfmt_misc.mount" not in receipt["stdout"]
  checks[path]=receipt["stdout"]
 receipt=run(prefix+["-c",'set -eu; mcopy -i "$1@@$2" ::/EFI/BOOT/BOOTX64.EFI /tmp/boot.efi; objcopy --dump-section .cmdline=/tmp/cmdline /tmp/boot.efi; cat /tmp/cmdline',"inspect","/input/"+image.name,str(efi)]);commands.append(receipt)
 assert receipt["returncode"]==0,receipt
 cmdline=receipt["stdout"].strip("\x00\n"); tokens=cmdline.split()
 assert [x for x in tokens if x.startswith("module_blacklist=")]==["module_blacklist=i8042,binfmt_misc"],cmdline
 assert not any(x.startswith("systemd.mask=") for x in tokens)
 result={"at":datetime.datetime.now(datetime.timezone.utc).isoformat(),"variant":d["variant"],"source":d["source"],"image_sha256":next(x["sha256"] for x in d["images"] if x["image"]==str(image)),"commands":commands,"status":"passed","uki_cmdline":cmdline,"checks":{"mount_unit_absent":True,"wants_link_absent":True,"variant_blacklist_preserved":True},"partition":{"offset":root,"length":blocks*blocksize,"sha256":hashlib.file_digest(partition.open("rb"),"sha256").hexdigest()}}
 (p.parent/"static-inspection.json").write_text(json.dumps(result,indent=2)+"\n")
 print(d["variant"],result["status"],cmdline,flush=True)
with concurrent.futures.ThreadPoolExecutor() as pool:list(pool.map(inspect,(BASE/"images").glob("*/inputs.json")))
