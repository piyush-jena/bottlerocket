# Issue 14 systemd guard validation, 2026-10-07

Historical checkpoint. The subsequent operator GPU-capacity waiver,
us-west-2 attempts, static NVIDIA inspection and cloud cleanup are recorded
in [the final validation report](../issue-14-final-validation/README.md).
Its results supersede the blocker and retained-resource status below.

GPU validation is blocked by EC2 capacity. All five fresh image builds and
private AMI registrations succeeded. Base mantle on both architectures and
FIPS on x86_64 passed boot, native container execution, and policy checks
before and after that execution. Base x86_64 also passed a direct filesystem
mount refusal and a reboot policy check. Neither GPU variant has booted or
run its smoke workflow for this revision; this is not final acceptance.

## Tested sources

- Bottlerocket `b26951c7cf95cd3cddf8ecefbbbc42162d89bdc2` plus the three-file
  temporary configuration recorded in `release-config.json` and the bundle's
  `runtime/test-configuration.patch`: release 1.66.1, its empty migration,
  and the local core-kit dependency. AMI names contain `symphony.14.r10`.
- Core-kit build source `f36d9c2bbc25887c07d7c8b79662b3944eb60ddc`, including
  product commit `fcaa82729f1f10519ce592ba54a1f710507c19c1`.
  `packages/systemd-257/systemd-257.spec` excludes the binfmt mount and
  wants-link from UKI images through package selection, as requested in
  the latest core-kit PR 3 review. The release-uki drop-in is removed.
- Published core-kit `17.0.1-symphony.14.build-f36d9c2b`, combined index
  `sha256:5ff08d597ba9aa781c8d760fb6fa9d59058bf6d4fbaf2dc666b286b5a09c6b9e`.
  Both inspected archive hashes and platform digests are in
  `registry-result.json`; the core-kit member's matching evidence directory
  contains the RPM ownership, dependency and solver checks.
- Twoliter `d2c650ad1489fe545f68c4fcbd481f2163ed5629`.
  `tool-verification.json` records each preserved binary's independently
  verified hash and build provenance. The existing full integration gate
  `fba33ee6-f05c-4a89-958b-4264f17a54fd` passed this unchanged source.
- Kernel-kit 9.2.0 and SDK 0.79.0 are unchanged. The live probes verified
  that binfmt_misc remains a shipped module and recorded its object hash.

## Results and identities

All resources are in account 533267423195, us-east-2.

| Variant | Architecture | Private AMI | Tested instance | Result |
| --- | --- | --- | --- | --- |
| aws-mantle-1 | x86_64 | ami-01945aec9e04a7d37 | i-03149ce5fa6c9952b | Passed, including reboot |
| aws-mantle-1 | aarch64 | ami-0a02773f67275735e | i-0d60151a84fd6d4e3 | Passed |
| aws-mantle-1-fips | x86_64 | ami-0ad5b2fd39f6ad7ad | i-04b3d0fd515aa69fa | Passed |
| aws-mantle-1-nvidia | x86_64 | ami-0815f12c43391c4c3 | None created | Capacity blocked |
| aws-mantle-1-nvidia-fips | x86_64 | ami-0a05dc5449a1f139e | None created | Capacity blocked |

The passing cases had exactly one effective
`module_blacklist=i8042,binfmt_misc` parameter. The mount unit and wants-link
were absent, `LoadState=not-found`, and explicit unit start failed as
expected. No failed boot units or binfmt module, filesystem or mount were
observed. Named modprobe, filesystem-alias modprobe and direct insmod failed
with `Operation not permitted`, with kernel blacklist messages recorded.
The same checks passed after native container execution.

The base x86_64 follow-up used
`mount -t binfmt_misc none /local/symphony14-binfmt-probe`.
It exited 32 with `unknown filesystem type 'binfmt_misc'`; the policy
remained effective. The temporary directory was removed. An EC2 reboot
completed, a different boot ID was observed, and the full policy passed
again. Commands, statuses and output are under `cases/` and in the bundle.

The native image digest is pinned in `image-pins.json`. The supplied forest
NVIDIA workflow and CDI merge hashes were checked against revision
`3e979b92109619605a0bd9a5f518e3673b1a4109`, but their GPU execution remains
pending. No historical drop-in or command-line-mask result is counted as
validation of the current package guard.

## Capacity blocker and cleanup

EC2 `RunInstances` returned `InsufficientInstanceCapacity` for 14 attempts:
g6.2xlarge in us-east-2a/b/c for both variants, g6.4xlarge in us-east-2b/c
for both variants, and g5.xlarge in us-east-2c for both variants plus
us-east-2a/b for NVIDIA. Candidate GPU counts and UEFI/NitroTPM support
were inspected where the instance family changed. The same verified AMIs
were reused. Every failed client token was reconciled with
`DescribeInstances`; no GPU instances were created.

`capacity-blocker.json` retains each launch input and error. The bundle
contains the exact launch output and reconciliation commands. These are
capacity failures, not product test failures. Resume when supported GPU
capacity is available in us-east-2; no image rebuild is required. Archive
the failed case directory after reconciling its client token before
retrying `run_case.py` against the retained AMI verification receipt.

All three completed test instances are confirmed terminated and their six
attached volumes deleted. Five private AMIs, ten backing snapshots, access
stack `symphony-14-systemd-guard`, and the issue-owned local kit registry
remain for resumption. Snapshot IDs are recorded per image in
`validation-summary.json`. The existing default VPC and subnets were
retained. The three temporary release/dependency files were restored to
their original bytes; `configuration-restored.json` records the hashes.

GPU boot/policy/native execution, the supplied smoke tests, final resource
cleanup and final PR updates remain unfinished. WIP must remain. The single
adversarial review already ran in the earlier round; do not request another.

## Evidence

`validation-summary.json` maps sources, compressed and expanded image
digests, AMIs, snapshot IDs, instances and 161 SSM command IDs to their
results. `commands-and-receipts.tar.gz` contains the complete retained
command output, build receipts, runtime scripts and cleanup records.
`bundle-manifest.json` hashes each entry; `bundle-receipt.json` hashes the
archive. Disk images, publisher binaries and raw HTTP debug traces are
excluded. This checkpoint deliberately reports blocked status.
