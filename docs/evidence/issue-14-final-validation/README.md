# Issue 14 validation after GPU capacity waiver, 2026-10-07

Base mantle on x86_64 and aarch64, and mantle FIPS on x86_64, passed fresh
boot, native container execution and effective binfmt policy checks.
The operator authorized proceeding without GPU capacity after requesting
us-west-2 g6.2xlarge. Those attempts also failed with insufficient capacity.
NVIDIA and NVIDIA-FIPS passed built-image inspection, but their runtime
policy, native-container and supplied GPU smoke tests did not run.
This report closes validation under that explicit coverage exception.
Registry removal is confirmed. The three PR updates are ready for the
conductor; no additional adversarial review is requested.

## Implementation and tested sources

The latest core-kit PR 3 review requested omission of the mount on UKI
images. Core-kit product commit
`fcaa82729f1f10519ce592ba54a1f710507c19c1`,
`packages/systemd-257/systemd-257.spec`, implements the image-feature guard
with a two-file binfmt subpackage. UKI images exclude the mount unit and
its wants-link. Non-UKI images select the subpackage. The shared kit RPM
build cannot use a variant-specific build-time conditional.

This supersedes the issue body's original `systemd.mask=` and base debug
generator prerequisite, as well as the intervening release-uki drop-in
and historical release-crypt policy. The release package is restored to
upstream. The four mantle variant definitions retain exactly one
`module_blacklist=i8042,binfmt_misc`; no kernel or firmware policy changed.

The five successful image builds used:

- Bottlerocket `b26951c7cf95cd3cddf8ecefbbbc42162d89bdc2`, plus the temporary
  three-file configuration patch SHA-256
  `f2d1ed1ecc93ac5cd92df444693a884302fbfb9b4a2c64fd467f722e07e4b0e1`.
  Release 1.66.1 has its empty migration entry. AMI names contain
  `symphony.14.r10`. The temporary release and dependency changes were
  restored to their original bytes and are excluded from product changes.
- Core-kit snapshot `f36d9c2bbc25887c07d7c8b79662b3944eb60ddc`, published as
  `17.0.1-symphony.14.build-f36d9c2b`, index
  `sha256:5ff08d597ba9aa781c8d760fb6fa9d59058bf6d4fbaf2dc666b286b5a09c6b9e`.
  Both platform archives, RPM ownership and requirements, all OCI layers,
  and the registry readback were verified. The core-kit member's
  `docs/evidence/issue-14-systemd-guard/` records the checks.
- Twoliter `d2c650ad1489fe545f68c4fcbd481f2163ed5629`, whose source tree
  matches current commit `aa8a122d1b3f085fa792b2181c599dc5de503467`.
  Full integration job `fba33ee6-f05c-4a89-958b-4264f17a54fd` passed.
  `tool-verification.json` identifies each preserved binary and its hash.
- Unchanged kernel-kit 9.2.0 and SDK 0.79.0. The shipped binfmt module
  remains present; `CONFIG_BINFMT_MISC=m` was not changed.

`final-validation-summary.json` maps each case to its exact build request,
source receipt, compressed and expanded image digests, AMI, snapshots,
instance and SSM command IDs. `regional-artifact-equivalence.json` verifies
that west registrations used the same NVIDIA image bytes as east.

## Runtime results

All resources were private in account 533267423195.

| Variant | Arch | Region | Instance | Result |
| --- | --- | --- | --- | --- |
| aws-mantle-1 | x86_64 | us-east-2 | i-03149ce5fa6c9952b | Passed, including reboot |
| aws-mantle-1 | aarch64 | us-east-2 | i-0d60151a84fd6d4e3 | Passed |
| aws-mantle-1-fips | x86_64 | us-east-2 | i-04b3d0fd515aa69fa | Passed |
| aws-mantle-1-nvidia | x86_64 | us-west-2 | i-09f6f9c55f0187a17 | Ordinary-instance fallback lacked GPU; runtime checks not run |
| aws-mantle-1-nvidia-fips | x86_64 | us-west-2 | i-0d283097985d51b34 | Ordinary-instance fallback lacked GPU; runtime checks not run |

The three passing cases had the exact blacklist, no mount unit or wants-link,
`LoadState=not-found`, and no failed boot units. Actual module, filesystem,
mount and registration state remained absent before and after native Busybox
execution. Named and filesystem-alias modprobe and direct insmod were refused
with kernel blacklist messages. A successful loader exit was never treated
as proof of module state. `image-pins.json` records the native image digest.

Base x86_64 additionally rejected a direct `mount -t binfmt_misc` with exit 32
and `unknown filesystem type 'binfmt_misc'`. Its temporary mountpoint was
removed. Reboot produced a different boot ID and the complete policy passed
again. There are 161 successful SSM invocations with response code 0; the
negative host commands and their expected nonzero statuses are retained in
those command outputs.

## GPU attempts and explicit coverage limit

`operator-update.json` preserves the operator's exact instruction to try
us-west-2 g6.2xlarge and proceed if unavailable. Earlier east attempts had
14 capacity refusals. West added five: both variants in us-west-2a, then
NVIDIA in us-west-2b, 2c and 2d. All were g6.2xlarge. Failed client tokens
were reconciled and no GPU instance was created.

Both west AMIs were then launched on m6i.large in us-west-2a. Their consoles
reported `NVRM: No NVIDIA GPU found`, driver-loading failures, and a failed
dependency for `configured.target`. SSM never became available. The local
readiness observers were stopped after recording that cause; they had sent
no SSM command. Console output and exact launch/readiness commands remain
in the bundle. These ordinary-instance attempts do not establish successful
NVIDIA boot or policy execution.

Both NVIDIA disk images passed offline inspection of the actual root
filesystem and UKI. The mount and wants-link are absent, binfmt_misc remains
a shipped module, and the UKI contains exactly one
`module_blacklist=i8042,binfmt_misc`. FIPS parameters are retained in the FIPS
image. Inspection used the already-present SDK without compilation or
network access. The first directory probe failed because dump.erofs does
not follow the `/usr` symlink; using the recorded physical sysroot path
resolved it. The unsuccessful probe and successful checks are both retained.
Static inspection does not replace the omitted GPU runtime coverage.

The supplied forest NVIDIA smoke and CDI merge scripts match revision
`3e979b92109619605a0bd9a5f518e3673b1a4109`; the image digest is pinned in
`image-pins.json`. Neither GPU smoke workflow ran for this revised packaging.
No historical mask or drop-in runtime result is counted as a current pass.

## Cleanup, review and evidence

Cleanup receipts confirm all five instances terminated, seven private AMIs
deregistered, fourteen snapshots deleted, and both issue-owned access stacks
deleted. Final region queries found no issue-owned images, snapshots or
volumes. Existing default VPCs and subnets were retained. Conductor job
`176f6e3a-19ac-8fa8-a9d4-19e0c8e742aa` removed the local kit registry.
`registry-clean-verification.json` records the successful receipt and
read-only Docker checks confirming the owned container and volume are absent.
No further compilation is needed.

One adversarial review already ran before the later human packaging request.
Its findings were addressed. The changed packaging was rebuilt and validated
as recorded here, including fresh negative mount and reboot checks. No second
adversarial review is requested. The final PR descriptions state the package
guard adjustment and GPU coverage exception and link the prerequisites.
With cleanup confirmed and review findings addressed, they request removal
of WIP. The prior review record is retained in
`../issue-14-uki-dropin/prior-review/`; its historical runtime results do not
validate the newer guard.

`commands-and-receipts.tar.gz` contains both regions' commands, outputs,
statuses, scripts, build receipts, static inspection and cleanup records.
`bundle-manifest.json` hashes each member and `bundle-receipt.json` hashes
the archive. Disk images, binary tools, private keys and HTTP debug traces
are excluded. The earlier blocked checkpoint remains historical in
`../issue-14-systemd-guard/`; this report supersedes its capacity blocker
and retained-resource status.

The command bundle is the immutable snapshot captured before registry
cleanup. Its internal summary therefore retains the then-pending registry
status. The adjacent final summary and `registry-clean-*` receipts include
the subsequent successful removal without rewriting the archived commands.
