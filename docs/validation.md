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

## P105 native HFS read-only cycle

A private ARMv7 prototype prepared a fresh 192 MiB HFSX image on 13G36. The
installed `fsck_hfs`, version `hfs-305.10.1`, completed its forced `-f -n`
scan and reported the expected volume clean. Its log included the explicit
`NO WRITE` marker and the full catalog, bitmap and volume checks. The child
exited successfully and its dedicated process group ended.

The first run retained its raw descriptor while the checker opened the same
node. Eject returned `EBUSY`. Apple's legacy driver increments its open count
for each open and resets that count at the final vnode close. A separately
reviewed recovery then opened one fresh descriptor, rechecked the same image
and issued one successful eject. The original run remains preserved.

The corrected prototype passed a complete cycle with another fresh copy.
After the checker finished, it closed the original raw descriptor and rebuilt
the ownership proof around the same registry IDs and device nodes. A fresh
descriptor matched both HFS headers and the sampled image sectors before
eject. The owned UUID, drive and media disappeared while every original media
ID remained present. The full image hash matched throughout, and the client
connection closed successfully. No filesystem mount or resize occurred.

The corrected build passed 335 host checks with service, child and eject
calls mocked. Its actual ARMv7 audit retained 93 imports, three system
libraries, minimum iOS 9.0 and zero lazy-binding entries. Root-controlled
runtime receipts separately establish the measured device result.

## P105 read-only mounted extents

The next private ARMv7 build passed a complete read-only mount cycle using a
fresh work copy of the same 192 MiB backup. A descriptor opened after mounting
proved the owned HFS source, mount path and device number. Both its filesystem
ID and the mount table agreed with the image's device identity.

Native `F_LOG2PHYS_EXT` calls used the measured 20-byte ARMv7 structure with
guard bytes. Sixty-seven queries covered the entire four-MiB sentinel and
rechecked its known mapping beyond the proposed 96 MiB boundary. Every mapped
range matched bytes from the saved image, and the complete sentinel hash
stayed unchanged.

All mounted HFS descriptors closed before normal unmount. The forced native
read-only filesystem scan then passed, followed by a fresh owned eject.
The original media remained present. Both complete image hashes matched the
original backup, and the controller client closed successfully.

The native mount program printed a re-key environment-check diagnostic while
returning success. Typed read-only mount and full data checks qualified this
unencrypted test image. Content-protected Data requires its own result.
The build passed 397 host checks with native operations mocked; its ARMv7
audit recorded 96 imports and zero lazy-binding entries.

## P105 native image shrink and restoration

A separate private ARMv7 helper issued one native shrink request on a fresh
writable image. The filesystem changed from 192 MiB to 96 MiB while the
virtual medium retained its original size. All four MiB of the sentinel moved
from beyond the proposed boundary to ranges below it, with its original
content hash. The mounted extent queries covered the file before and after
the request. Normal unmount, forced native read-only checking and owned eject
all passed.

The changed image was copied to the Mac with its detached native hash intact.
The Swift inspector and independent reads matched the primary header, the
new filesystem-end alternate and the retained medium-end alternate. Each
reported HFSX version 5, 4,096-byte allocation blocks and 24,576 blocks.
Sixty-four recorded relocated ranges reproduced the complete sentinel hash
from the host copy. A read-only attachment also passed the Mac filesystem
checker and retained its full image hash after detachment.

The host initially expected an earlier stdout marker and refused completion.
The native run had already passed every journal field and returned success.
The corrected host check finalized those saved receipts through read-only
file transfers, with zero additional native helper invocations. Four captured
protocol checks cover acceptance of that actual output and refusal of missing
proof or a failed resize.

A fresh restoration then copied the original protected backup into another
image. Its full hash matched the original 192 MiB input. Native read-only
mount, original extent mapping, filesystem checking and owned eject passed.
Readback afterward confirmed that the changed 96 MiB work image and its
manifest and journal retained their hashes.

The shrink build passed 2,494 host checks with resize and storage calls mocked.
The restore build passed 6,561 such checks. Their actual ARMv7 import audits
and signed launch gates passed separately from the device experiments.
This measured case covers the unencrypted disposable image. Native durable
stop cases, content-protected physical volumes and LwVM writes need further
qualification. Kernel power loss during an in-flight resize remains untested.
Private owner inputs, device captures and generated disk images stay outside
this repository. The published iOS command continues to supply passive
inventory while active prototypes undergo these tests.

## P105 bounded native LwVM snapshot

A separate private ARMv7 helper captured metadata through the existing native
iOS logical media. It bound the selected P105's whole 64 GB medium, LwVM view
and System/Data slices through their typed registry ancestry, BSD device
numbers and 4,096-byte geometry. The device descriptors stayed read-only.
Sixteen aligned reads requested a total of 65,536 bytes, within its 160 KiB
budget. Private output files retained the captured ranges and their hashes.

Both physical 4 KiB LwVM headers passed CRC32 and matched byte for byte.
The second lies at byte 67,104,768 for this measured geometry. Each header,
the virtual GPT headers and their mirrored entry arrays matched again after
the live HFS reads. Registry identities and device geometry remained stable;
all raw descriptors closed and registry releases passed. System and Data
reported journaled HFSX version 5. Data also had content protection enabled.
The mounted HFS observations retain their live scope and were never frozen
or filesystem-checked by this snapshot.

Independent host checks reproduced both physical-header checksums with
Python zlib and the new Swift saved-header diagnostic. The existing revision-1
fixture checker also passed both virtual headers and the mirrored logical
entry arrays. This native view declared two 128-byte records inside each
aligned 4 KiB capture. Separate 256-byte copies supplied the exact-array
fixture interface; the original captures stayed intact. Their remaining
padding was zero. The initial direct padded-file refusal remains recorded.

The native helper passed 339 sanitizer-backed host checks with native calls
mocked. Its actual ARMv7 binary had 44 imports and zero lazy-binding entries.
The same signed artifact passed a no-argument launch on 13G36 before its one
snapshot invocation. An earlier SSH readback failed before helper launch;
a fresh read verified the complete uploaded binary, then resumed that launch.
Private receipts preserve both attempts.

The portable suite now passes 45 tests on macOS. Six command checks exercised
the independently calculated fixture, a corrupt final byte and refusal of
unsupported file types while preserving the input. Snapshot agreement covers
the observed ranges and interval. Physical allocation semantics, durable
LwVM updates, content-protected resizing and Linux internal storage remain
open.
