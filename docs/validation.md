# Phase 5 validation

Recorded on 28 October 2026. The new project carries the saved-file inspectors
and synthetic fixtures from the preserved research into a standalone personal
repository.

## Host checks

| Check | Measured result |
| --- | --- |
| Imported baseline | 33 Swift tests passed before new code was added |
| Current Swift suite | 40 tests passed on macOS with Swift 6.4 and Linux ARM64 with Swift 6.0.3 |
| Image lab unit suite | 20 Python tests passed on the Mac |
| Passive-helper audit | 12 tests passed, including an altered Mach-O with an active-I/O import that was refused |
| Native helper | ARMv7, minimum iOS 9.0, two system libraries and the reviewed 13 imports |
| Original source | Preserved copy and original working source matched before import; original files remain unchanged |

Linux Swift checks used the official `swift:6.0.3-jammy` multi-architecture
image at digest `sha256:95f6ef898992dc840b35517e780f6f6db9661432775ab0b33cc0a531ea749bdb`.
The project source was mounted read-only and compilation used container-local
scratch space with networking disabled.

## macOS HFSX image experiment

The host was macOS 27 with Xcode 27.1. Each run created a fresh 192 MiB HFSX
image and proposed a 96 MiB filesystem. The virtual medium retained its
192 MiB geometry. A four-MiB file started beyond the proposed boundary; after
shrinking, its extents lay below that boundary and its full content hash
matched.

The clean run passed a read-only reattach and `diskutil verifyVolume` after
detachment. The backing image's hash stayed unchanged during that verification.
The Swift complete-image inspector independently matched the primary and
filesystem-end alternate header geometry in the shrunk and restored files.

Whole-image backup restoration passed after a clean shrink and after each
durable stop: `backup-verified`, `shrink-requested` and `shrink-returned`.
Every restored file matched the original backup hash and passed its own
read-only sentinel and filesystem checks at the original size. A separate
restore also recovered the image from an early verification failure after
the shrink had returned.

Native refusal tests changed the proposed device, image inode and target size.
The helper refused each case while the image retained its original size.
Review also found two lab defects that were fixed: failed calls now retain
both output streams and their exit status, and access evidence requires
explicit booleans. Unit tests cover those failures and a timed-out call
leaving the mutation checkpoint unresolved.

The stop cases test the supervising process at durable checkpoints. Kernel
power loss during an in-flight resize remains untested.

## P105 read-only result

The signed passive helper ran on `iPad2,5` / `13G36` through the owner's
verified iOS SSH connection. It reported one exact `IOHDIXController` and the
expected ARMv7 widths. Its source and output kept user-client opens and image
attachments outside this run. Temporary files were removed afterward.

Native iOS image attachment and shrinking remain unqualified. LwVM writes
and internal Linux storage require their own evidence. Private owner inputs,
device captures and generated disk images stay outside this repository.
