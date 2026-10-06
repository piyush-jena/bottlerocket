# Issue 14: UKI drop-in acceptance, 2026-10-06

Fresh private AMIs passed boot, effective binfmt policy and native container
execution on all five required cases. Both GPU cases passed the supplied
NVIDIA deviceQuery and vectorAdd smoke tests. The same 38 policy checks
passed before and after containers in each case. These results validate
the UKI drop-in revision requested in Bottlerocket PR 16 comment 881.

## Sources and reviewed adjustment

- Bottlerocket `3f1f18e74640c671872a6b114bd42dddb612ea68`,
  `variants/aws-mantle-1*/Cargo.toml`: all four variants extend the existing
  parameter to `module_blacklist=i8042,binfmt_misc`.
- Core-kit `fa6d388f834b2c370fed8f61c6c7145a20c0bab0`,
  `packages/release/release.spec` and `binfmt-misc-mount-uki.conf`:
  `release-uki` is selected by `image-feature(uki-image)` and owns
  `proc-sys-fs-binfmt_misc.mount.d/10-uki.conf`.
- This implements the human review adjustment using
  `[Unit] ConditionPathExists=!/`. Root exists, so the mount is skipped
  at boot and on explicit start. It is loaded/inactive with
  `ConditionResult=no` and `Result=success`, not `LoadState=masked`.
  `ExecCondition` is a service directive, so the mount uses a unit condition.
  Command-line `systemd.mask=` and the base-package debug-generator
  prerequisite were removed. The superseded release-crypt policy is absent.
- Twoliter `d2c650ad1489fe545f68c4fcbd481f2163ed5629` preserves the
  blacklist through UKI assembly. Its tree equals current PR revision
  `aa8a122d1b3f085fa792b2181c599dc5de503467`; no tool code changed.
- Kernel-kit `cf5b162a0da6a91132d282e32a426851afb29683`,
  kernel-6.18 x86_64/aarch64 configs: `CONFIG_BINFMT_MISC=m` remains.
  Consumed kernel-kit 9.2.0 and SDK 0.79.0 were unchanged.

The tested product has exactly three recorded temporary configuration
changes: Release.toml, Twoliter.toml and Twoliter.lock. They declare numeric
1.66.1, the empty (1.66.0, 1.66.1) migration and the issue-tagged core kit,
as explicitly required by the issue. BUILD_ID is `3f1f18e7-dirty`.
The immutable build inputs were checked against the recorded file hashes
and patch before registration. All three files were restored to HEAD
after all five builds completed. They are evidence, not product changes.

See [release-config.json](release-config.json) for exact file hashes,
[test-configuration.patch](test-configuration.patch) for every changed byte,
and [kit-publication.json](kit-publication.json) for both verified archives
and OCI platform digests. The consumed core-kit version is
`17.0.1-symphony.14.build-fa6d388f`, index
`sha256:92e8ca62c4b3244aef4e48d892a48670e15c0cf04327cfdd1c008e302f4c1545`.

## Live matrix

| Variant | Architecture | AMI | Instance | Container result |
| --- | --- | --- | --- | --- |
| [aws-mantle-1](cases/aws-mantle-1-x86_64/result.json) | x86_64 | ami-019bb8caaf77b3463 | i-02393698098b1c108 | native PASS |
| [aws-mantle-1](cases/aws-mantle-1-aarch64/result.json) | aarch64 | ami-0df3f6053844bc807 | i-0ab72aa43e1cee521 | native PASS |
| [aws-mantle-1-fips](cases/aws-mantle-1-fips-x86_64/result.json) | x86_64 | ami-00f2b4235b558b774 | i-04b39cc386d65f0d9 | native PASS |
| [aws-mantle-1-nvidia](cases/aws-mantle-1-nvidia-x86_64/result.json) | x86_64 | ami-0c7235b305234a123 | i-063fae68a34d43e3a | deviceQuery PASS; vectorAdd PASSED |
| [aws-mantle-1-nvidia-fips](cases/aws-mantle-1-nvidia-fips-x86_64/result.json) | x86_64 | ami-00a1be9870b34c930 | i-0788bbca00e537a35 | deviceQuery PASS; vectorAdd PASSED |

All AMIs were private in account 533267423195, us-east-2, with UEFI and
TPM v2.0. Their names include `symphony.14.r10`. Per-case inputs.json
records compressed and decompressed OS/data image SHA-256 values, UEFI
data, the publisher hash and exact registration arguments. Build input
digests, job IDs and SSM command IDs are in
[validation-summary.json](validation-summary.json).

## What the checks establish

Each fresh boot reports the exact release/build identity, one effective
blacklist, the UKI feature and the expected packaged drop-in. The module
object is still shipped, but binfmt_misc is absent from /proc/modules,
/proc/filesystems, mounts and /sys/module. Named modprobe, filesystem-alias
modprobe and direct insmod are rejected; module state is checked afterward.
An explicit mount-unit start returns without mounting it or failing the
unit. Relevant boot units and failed-unit state are checked. The settings
allow binfmt_misc with autoload disabled, demonstrating that the tested
kernel blacklist is effective even with the settings permission present.

The same probe runs after native container execution, with the boot ID
unchanged. Each policy-before.json and policy-after.json contains check
results and exact command arguments, exit status, stdout and stderr.
Successful modprobe exit alone was never used as evidence.

The native cases print `R10_NATIVE_CONTAINER_PASS` and the expected
architecture from the pinned BusyBox image. GPU cases run the supplied
bottlerocket-forest main script and CDI merger unchanged; only SSM
transport is adapted to retain full output and verified OCI spec delivery.
Both report one NVIDIA L4, deviceQuery `Result = PASS` and vectorAdd
`Test PASSED`. See [image-pins.json](image-pins.json),
[workflow-source.json](workflow-source.json) and each GPU stdout file.

Initial g6.xlarge launches failed with InsufficientInstanceCapacity in
us-east-2a, us-east-2b and us-east-2c. Client-token queries confirmed no
instances were created. Both GPU cases then used g6.2xlarge in the existing
default us-east-2c subnet, retaining one NVIDIA L4 and the same AMI,
security group and role. All failed attempts and recovery commands are
preserved in the bundle under runtime/capacity-recovery.

## Gates and cleanup

Both core-kit architecture builds passed. Offline RPM inspection verifies
exclusive drop-in ownership, the conditional feature dependency and
no-UKI conflict. The packaged mount parses; its condition passes without
the drop-in and fails as expected with it. These are composition/offline
checks, not a claim of a fresh non-UKI EC2 control test.

All five new image builds passed. The full Twoliter integration gate
`fba33ee6-f05c-4a89-958b-4264f17a54fd` passed 19 tests on the unchanged
tool revision. The fresh required `make -C /home/fedora/Repositories/symphony
integ` gate passed with exit 0; [gate-result.json](gate-result.json)
records its output digest. No harness code or configuration was changed.

All five instances were terminated, five AMIs deregistered, their ten
snapshots deleted, and the issue access stack removed. Final queries
found no issue-tagged AMIs, snapshots or volumes. Existing default VPC
and subnets were retained. See [ec2-cleanup.json](ec2-cleanup.json).
Registry cleanup is requested through the conductor; its receipt is
still pending at this report milestone.

Both GPU shutdown consoles reached `reboot: Power down`. They also
reported busy filesystem/device teardown and `mdadm.shutdown` exit 1.
These occurred after the successful live checks; the raw consoles are
preserved under runtime/shutdown-observation. This work does not establish
the cause of those shutdown warnings. EC2 continued to report
`shutting-down` after guest power-down, so cleanup used
`terminate-instances --force --skip-os-shutdown` for the two verified
issue-owned GPU instance IDs. The request and final states are recorded.

This revision did not rerun reboot tests or non-UKI EC2 controls. Those
belong to superseded validation and are not claimed here. Firmware-variable
restrictions remain in issue 11. The earlier final adversarial review
was already addressed; no additional review round was requested.

## Reproducible command evidence

[commands-and-receipts.tar.gz](commands-and-receipts.tar.gz) contains the
runtime scripts, exact SSM commands/IDs/results, complete stdout/stderr,
image registration and cleanup receipts, immutable input attestations,
kit RPM inspections and build/gate logs. It excludes disk images, RPMs
and publisher binaries; their hashes are retained.
[bundle-manifest.json](bundle-manifest.json) records every included file
with SHA-256 and size. Runtime scripts can create cloud resources and
should be inspected before reuse.

Bundle SHA-256: `2eadfad43ab54475e1101bdb24585dcf54350024b1aeb6c25e520f1b2659da5f`.
