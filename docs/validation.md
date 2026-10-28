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
| Passive-helper audit | 13 tests passed, including an altered Mach-O with an active-I/O import that was refused |
| Passive counter failure paths | 19 host C cases passed with 2,233 checks against the actual source; registry functions were mocked and external registry imports were refused |
| Native helper | ARMv7, minimum iOS 9.0, two system libraries and 14 required imports; legacy linkers may add the reviewed lazy binder |
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

The same clean and stop/restore scenarios passed on a hosted macOS 15 runner
in [image-lab run 40716427858](https://github.com/shaynelegault/resize-hfs/actions/runs/40716427858).
Its uploaded artifact contains the aggregate JSON summary. Generated disk
images remain outside the repository and workflow artifacts.

## P105 read-only result

The signed passive helper ran on `iPad2,5` / `13G36` through the owner's
verified iOS SSH connection. It reported one exact `IOHDIXController` and the
expected ARMv7 widths. Its source and output kept user-client opens and image
attachments outside this run. Temporary files were removed afterward.

The first version categorized a successful match with a null iterator as
unavailable. After correcting that documented empty-match case, a second
signed run reported zero exact `IOHDIXHDDriveInKernel` instances and retained
the same 13-name import set. Its output again recorded no client open or
image attachment, followed by removal of its temporary files.

The later signed revision preserves explicit MIG next/validity status. It
reported one exact controller and zero drive instances, with a valid
`kIOReturnNoDevice` result accepted as the end of iteration. Its required
import set contains 14 names. The host counter tests exercise partial RPC
failure, invalidation at several stages, successful null iterators, class
failures and inspection bounds. Combined passive test discovery passes 14
Python test entries, including the C harness runner.

A separately reviewed private access experiment then opened a type-0 client
on that unique controller as root and closed it. Both calls returned success.
It issued no external method request, and its temporary executable and report
were removed. This result establishes client access for the tested build;
image attachment and its lifetime require the next experiment. The published
passive helper retains its narrow import set and audit policy.

## P105 isolated image lifecycle

A private prototype created a new 8 MiB regular fixture and submitted one
mode-1 selector-5 request on 13G36. The fixed-width input used 256 bytes, with
64-bit buffer fields at offsets 8 and 16. The kernel returned success and a
four-byte IOUnit. A fresh identifier and copied image path matched the new
KDIURL and drive properties.

The first media guard stopped before raw access because two baseline media
needed 17 parent edges to reach the registry root. Passive inspection found
one new whole image medium with the expected size, 512-byte blocks and
complete ownership ancestry. A separately reviewed helper then targeted that
existing instance using the pinned file hash and original journal. It matched
the nonce through its retained read-only raw descriptor and issued one eject.

The owned KDIURL, drive and media disappeared. Every original media ID stayed
present, and both the full fixture hash and original journal hash matched
afterward. The fixture and receipts remain available privately. This trial
qualifies the measured inert-image path. Its active prototypes retain their
research status while the published helper supplies passive inventory.

Native iOS HFS filesystem checking and shrinking remain unqualified. LwVM
writes and internal Linux storage require their own evidence. Private owner
inputs, device captures and generated disk images stay outside this repository.
