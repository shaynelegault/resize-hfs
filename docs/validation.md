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

## macOS shrink and grow-back cycle

On 4 November 2026, the updated image lab completed 192 MiB to 96 MiB to
192 MiB on a fresh HFSX fixture. Both resize calls returned zero. The
four-MiB sentinel retained its hash, and independent header reads matched
each resulting size. Separate read-only reattachments and full filesystem
checks passed after shrink and growth without changing the backing image.

The grow helper refused altered device, inode, shrink-target and grow-target
receipts before changing the filesystem. Whole-image backup restoration
passed after the clean cycle and after five stops: backup verification,
shrink intent, shrink return, grow intent and grow return. Each restore used
a fresh file and passed read-only verification at the original size.

The image-lab unit suite now has 25 passing tests; full Python lab discovery
passes 63. Growth failure and timeout tests preserve the uncertain request
and its output without replay. The manual macOS workflow now includes
`--grow-back`; the six-case result above came from the local Mac. The native
iOS image-growth result appears below. Power loss during a resize remains
unqualified.

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

## P105 native image growth

On 4 November 2026, a fresh ordinary-file seed bundle reproduced the captured
native-shrunk image, including its complete hash and original shrink records.
The seed contains a 96 MiB HFSX filesystem in a 192 MiB backing file. A new
ARMv7 helper copied it into a fresh work image and issued one native grow
request to 192 MiB. The request returned zero. Its original seed remained
read-only and passed repeated full-image hash checks.

The helper made 131 extent queries across the pre/post checks. All four MiB
of the sentinel retained their content hash; their first physical byte stayed
at 11,550,720. Primary and filesystem-end alternate headers reported 49,152
allocation blocks of 4,096 bytes. Normal unmount succeeded. Native
`fsck_hfs -fn` checked the full filesystem successfully, and the helper ejected
its owned image, verified removal of its graph and closed its controller.

The exported 201,326,592-byte image matched its detached native SHA-256:
`216f139b0689e0976f94fa3be3ae1c15d49e8e7d8ab5d3acf6d37e669f581129`.
The public Swift inspector independently confirmed 192 MiB HFSX geometry
with zero trailing bytes. Host reads reproduced the complete sentinel hash
from the exported file. The helper passed 2,514 host checks under sanitizers;
five receipt-validator tests covered incomplete records and failed resize,
cleanup, data and geometry proofs before device execution.

This qualifies growth of the unencrypted disposable image on iPad2,5/13G36.
Content-protected internal volumes and provider expansion need their own
qualification. The active helper remains a private prototype; the public
iOS interface continues to expose passive inventory.

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

## P105 RAM recovery and raw-device admission

Boot9 and boot10 used the same frozen 32 MiB recovery image and its ephemeral
one-byte kernel change. The checked loader required a fresh blue-screen
observation. Its `bootx` control returned an uncertain byte count, followed
by a USB mode change. A matching custom USB serial, pinned SSH host key and
image marker then established the running image. Both boots passed the signed
native status check for iPad2,5 build 13G36. `/dev/md0` was the writable root;
devfs was the only other mount. System and Data were unmounted.

Boot9's first recovery snapshot stopped at registry binding with zero device
reads. A signed passive inspector found that System media reports
`Writable=true` in this unmounted recovery state, where normal iOS had
reported false. A separate one-field candidate passed 389 host checks and
retained the original 48 imports. Its target run passed the graph check and
stopped during read-only device open, again with zero device reads.

Boot10's fixed-path diagnostic tried one `O_RDONLY` open on each of
`/dev/rdisk0`, `/dev/rdisk0s1`, `/dev/rdisk0s1s1` and `/dev/rdisk0s1s2`.
All four returned `EPERM` (errno 1). The nodes had the expected device
numbers. A separate policy probe reported effective UID 0,
`kern.securelevel=0`, and `security.mac.device_enforce=1`. Its temporary
sysctl change returned `EPERM`; readback stayed at 1. Normal iOS also
reported `device_enforce=1` and `vnode_enforce=1`, so those values alone do
not identify the kernel check that denied the recovery opens. Normal iOS
reported `proc_enforce=0` while recovery reported 1. A zero-count normal-iOS
command opened `/dev/rdisk0` and closed it without a read. Private attempt9
and attempt10 receipts hold the exact signed binaries, SSH outputs and cleanup
results.

Boot11 used a separate 32 MiB image. Its kernel candidate changed two exact
13G36 Thumb instructions that load `MAC_ALL_ENFORCE` during credential updates,
masking the `0x0080` vnode bit from newly applied flags. Apple’s published
[XNU 3248 source](https://github.com/apple-oss-distributions/xnu/tree/rel/xnu-3248)
guided the change; that source is revision 3248.60.10 while
the iPad reports 3248.61.1. Its per-process enforcement check is compiled
only for debug builds. The iPad identifies its kernel as a release build, so
the candidate's access premise lacked support in that published source. The
host build checked the original bytes, symbols, disassembly, IMG3 roundtrip,
embedded image files and read-only
filesystem consistency. The candidate did not clear flags already held by a
process.

The checked loader sent the candidate after a fresh blue-screen observation.
Its control return at the USB transition remained uncertain, followed by
the pinned recovery serial, SSH host key and image marker. The signed status
check reported iPad2,5/13G36, writable `/dev/md0`, devfs, and System and Data
unmounted. One signed diagnostic tried the four raw nodes; another tried
`/dev/disk0`, `/dev/disk0s1`, `/dev/disk0s1s1` and `/dev/disk0s1s2`.
All eight read-only opens returned `EPERM` before any device read or write.
The recovery helper scratch was removed. Normal iOS returned on the original
USB port, SSH and its usual mounts passed, and the owner confirmed the unlocked
home screen. The denial site remained unproven at that stage. The private attempt11 receipt
records the exact inputs and results.

A separate zero-count command opened `/dev/rdisk0` after the return to normal
iOS. It transferred zero bytes and closed successfully. Its saved mount list
matches the return-path receipt. This confirms the normal-iOS access difference
persisted after the recovery reboot.

A matched normal-iOS helper used the recovery diagnostic's `O_RDONLY`,
`O_NOFOLLOW`, `O_NONBLOCK` and `O_CLOEXEC` flags. Its first run opened the
whole disk and LwVM nodes. A fixed minor-number guard skipped System and Data:
their `st_rdev` values were 3 and 2 in normal iOS, compared with 2 and 3 in
RAM recovery. A second signed helper changed only that guard. It opened and
closed all four raw nodes successfully. Both normal-iOS helpers made zero
device reads or writes and removed their temporary files. This comparison
isolates a boot-environment difference in raw open admission.

Boot12 then used a diagnostic kernel built from the root-writable image.
The exact target wrapper at `0x8038d508` invokes the MAC vnode-open policy
callbacks. Its two EPERM selectors returned marker 80 in this image. Host
emulation compared 335 cases with the original routine and preserved each
success or denial. In the verified RAM boot, all four raw opens returned
80 while performing zero media reads or writes. That result locates the
refusal in the MAC open-policy wrapper. Normal iOS, SSH and the unlocked home
screen returned afterward. The two earlier process-flag edits are absent
from this diagnostic image.

Boot13 used a scoped exception in that wrapper. It preserves policy callback
order and error selection, then admits EPERM-denied read-only opens for
effective UID 0 on character devices with BSD numbers `0x01000000` through
`0x01000003`. The flag filter permits FREAD with optional nonblocking,
no-follow and close-on-exec bits. The original and candidate routines passed
1,447 paired host cases, including the target credential and vnode accessors.
Other results and write-open behavior stayed unchanged in those host tests.

The candidate's USB serial, SSH key and image marker matched the prepared
image. Signed native status reported writable `/dev/md0` and devfs as the
complete mount set. All four raw nodes opened and closed successfully.
The subsequent signed snapshot helper completed 16 reads totaling 65,536
bytes. It checked the primary and backup physical LwVM CRCs and equality,
repeated virtual GPT tables and unmounted HFS prefixes, and rechecked the
storage graph. Every raw descriptor closed. Exported files passed independent
host checksum and geometry checks. The two LwVM headers and four GPT metadata
blocks matched the earlier normal-iOS capture byte for byte. At that point, the measured
Data filesystem was 60,701,716,480 bytes; the later physical shrink is recorded
below.

Recovery later returned to normal iOS. Its reset log records `Boot faults:
wdog` and one boot failure, about ten minutes after kernel delivery. SSH and
the usual iOS mounts passed; the owner confirmed the unlocked home screen.
The next helper had uploaded into RAM but stopped at a missing `/bin/chmod`
command before launch. Its native writer-open operation never dispatched.
Subsequent preparation uses the existing SFTP permission operation.

A separate image adds the volatile `wdt=-1` boot argument. Host work reproduced
the previous iBEC exactly, confined its eight changed bytes to that argument,
checked the unchanged watchdog code spans in the candidate kernel, and
verified the new image with read-only fsck.

Boot14 used that image and repeated the four raw opens and bounded snapshot.
The physical headers and GPT metadata matched boot13. The signed watchdog
observer verified `wdt=-1`, one exact `AppleS5L8930XWatchDogTimer` service and
typed `IOWatchDogDisabled=true`. A second observation at uptime 1,452 seconds
matched the first observation's boot time and registry identity, 908 seconds
after its uptime-544 capture. Both observations checked RAM-only mounts, and
USB/SSH remained available. The observer required fixes for iBEC's appended
`backlight-level` argument and the iterator's native end result. Host checks
cover 132 argument cases and 65 iterator cases.

The open/close parent's first attempt stopped before launching its child.
Its prepared-record decoder rejected the high-bit devfs identifier
`0xb98094d4`, although the wire format stores all 32 bits of Darwin's signed
`dev_t`. The original decoder reproduces the refusal against the captured
manifest. A corrected variant passes 5,890 native host checks and 244 codec
checks, including the captured record, device-ID boundaries and overflow
rejection. Its wrapper passes 20 tests and three deliberate guard mutations;
the device runner passes 14 host tests.

A fresh RAM lease then completed one supervised `O_RDWR` attempt on
`/dev/rdisk0s1`. The read-only recovery kernel returned `EPERM`. The child
exited with status zero and was reaped; its process group was absent.
Six graph observations completed, the graph matched afterward, and all ten
sampled metadata windows remained byte-identical. Host exports verified the
nonce-bound child result, the saved preimages and the post-operation windows.
The parent requested 98,304 bytes during this phase and issued no explicit
device write. This qualifies the refused-open control.

Boot15 added a scoped plain `O_RDWR` admission for the LwVM container's raw
node, retaining the existing read-only rule. The first accepted open returned
descriptor 6 and closed successfully. System and Data disappeared and were
recreated with their BSD minor numbers exchanged. The original parent's
fixed-number check failed. Its child result and a separate bounded snapshot
proved the close and equality of all ten sampled areas; the original failed
result remains preserved.

The corrected helper binds each leaf's device number to its typed registry
properties, allows only the distinct minor-number pair 2/3, and retains the
partition ID, size, base and ancestry checks. A follow-up launch stopped
before sending permission to open because its executable path still selected
the prior helper. That case preserved its evidence and reaped the child.
The corrected launch path now derives from the same lease definition and
must identify the verified executable before spawning it. Host checks passed
6,171 native mock assertions, 244 codec assertions, 20 wrapper tests and 14
driver tests. Three wrapper mutations were rejected.

The fresh completed case made one accepted open and one successful close,
with a zero-status child reaped and its process group absent. Six registry
observations captured partition teardown and recreation. The helper rematched
the children and compared all ten pre/post metadata files successfully. The
action requested 98,304 read bytes and made zero explicit device writes.
Host exports verified the child result and unchanged samples, which also
matched the first boot15 preimage. The watchdog remained disabled at uptimes
115 and 1,781 seconds with USB/SSH access. Native commit recovery remains
unqualified; this test covers the plain open/close lifecycle.

The recovery runs so far issued no physical HFS resize, LwVM update or NAND
program/erase request.

## P105 physical Data shrink

On 4 November 2026, the iPad2,5/13G36 test device completed one native
`ffsctl(0x80086802)` request to shrink mounted Data from 60,701,716,480 bytes
to 42,949,672,960 bytes (40 GiB). The call returned zero. Data reported
10,485,760 blocks of 4,096 bytes afterward, and all 21 owned descriptors
closed successfully. The helper exported its completed durable journal.

Four 64 KiB ordinary test files, one for each protection class A/B/C/D,
occupied measured extents above 40 GiB before the request. Their containing
directory resides directly below `/private/var` and survived a normal reboot.
A fresh process verified each file's complete contents before the shrink.
That reboot exchanged System and Data's BSD minor numbers. The corrected
verifier binds current device numbers to the mounted Data filesystem while
retaining the saved file identities and content checks.

After the resize, the four extents began at 1,879,101,440, 1,879,166,976,
1,879,232,512 and 1,879,298,048 bytes. Each complete SHA-256 matched its
pre-resize value. Protection class, inode, size and timestamps also passed.
The helper retained its ticket and journal on Data and removed its uploaded
executable after host export.

A separate read-only check fetched 20,480 bytes through the raw device nodes.
The primary HFSX header, the alternate at the new filesystem end and the
alternate at the unchanged provider end all reported 40 GiB. The live primary
free-block count differed from the alternates during mounted iOS activity;
this capture does not establish an atomic filesystem snapshot. Both physical
LwVM header blocks matched the boot15 preimages byte for byte. The Data
partition remains 60,701,716,480 bytes, with no Linux partition allocated.

The native helper passed 474 sanitizer-backed host checks. Its host stage
passed 22 tests, and ten native guard mutations plus three wrapper mutations
were rejected. Device receipts retain the preflight ticket, the single-call
result, the completed 14-event journal and the independent header captures.

A later RAM recovery boot completed forced read-only filesystem checking,
as recorded below, followed by successful normal-iOS verification of the
protected files and reduced size. Recovery after an interrupted physical
resize remains unqualified.
Internal Data growth and the LwVM partition update require separate tests.
This run used Apple's mounted HFS and flash stack; Linux NAND writes remain
outside its measured scope.


## P105 unmounted Data check after shrinking

Boot16 reused the verified v11 recovery image. Its USB identity, SSH key and
build marker matched. Signed native status reported only writable `/dev/md0`
and devfs mounted, with System and Data unmounted. A typed watchdog query
confirmed `wdt=-1` and the disabled watchdog at uptime 89 seconds.

The first helper stopped at its RAM-directory guard before spawning fsck.
That guard had treated the directory link count as fixed. The RAM HFS volume
reported three links after the log was created, which invalidated its saved
empty-directory count. The failed attempt closed its descriptors and reported
zero device writes. A corrected helper keeps the directory's device, inode,
type, owner and mode bound while allowing its entry count to change. Regular
file link counts remain strict. It passed 136 sanitizer-backed host checks;
mutations restoring the directory-count bug or weakening file link checks
were both rejected.

The corrected helper created a fresh RAM directory and issued one
`fsck_hfs -f -n /dev/rdisk0s1s2` invocation. Apple's hfs-305.10.1 checker ran
through the catalog, extended attributes, allocation bitmap and volume
information checks, reporting `The volume Data appears to be OK.` Its child
returned zero, was reaped and left no process group. The helper reported
zero device writes, close errors or timeout errors.

The primary HFS header, the alternate at the 40 GiB filesystem end and the
alternate at the unchanged partition end all reported 10,485,760 blocks of
4,096 bytes. Each sampled 4 KiB block matched before and after fsck. Both
physical LwVM header blocks also matched, including their boot15 hashes.
The host retained 40,960 bytes of samples across both captures and validated
the complete checker log. This byte count excludes the checker's own reads.

The Data partition remains 60,701,716,480 bytes. Physical partition updates
and recovery after interrupted writes require separate tests.


## P105 return to iOS after the physical shrink

After boot16's completed read-only check, the iPad rebooted to normal iOS.
USB and SSH returned, and the mount table showed System, Data and devfs.
The persistent protected-file directory and the completed resize records
were present. The transient boot directory had been removed by iOS.

A signed verification-only helper reopened the four original 64 KiB files
in a fresh process. Data reported 10,485,760 blocks of 4,096 bytes. Each file
retained its original full SHA-256, protection class and inode; the saved
manifest's timestamp checks also passed. Their extents remained at the
post-shrink offsets below 40 GiB. The complete original manifest hash matched.
This helper issued zero resize and allocation requests.

The native verification returned zero. Its host reader then requested the
old v4 report filename, and the version check rejected that report. A separate
export step fetched the saved v5 report and validated it against the original
manifest and four complete payload hashes. It launched zero native helpers
and removed the hash-verified uploaded probe after completion. The original
failed export remains preserved. Eighteen host checks cover stale-report
rejection, identity and hash mismatches, changed allocation claims and invalid
extent maps. The ARMv7 verification source passed 1,603 sanitizer-backed host
checks before its device invocation.

A final bounded read exported the retained 4,096-byte preflight ticket and
6,643-byte resize journal. Both matched their complete pre-reboot hashes.
The ticket remains consumed. These saved records describe the completed
operation and preserve its evidence across the recovery boot.
