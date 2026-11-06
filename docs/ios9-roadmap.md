# iOS 9 and P105 qualification

The target is `iPad2,5` / P105AP running iOS 9.3.5 build 13G36. Earlier read-only
research found HFSX System and Data volumes behind LightweightVolumeManager.
The partition-facing view reported `EFI PART` with revision `0x00000001` and
4,096-byte logical blocks. The Swift tools retain that raw revision in their
diagnostics.

The portable commands run on the development host. The image helper is a
macOS program that requires Disk Images and Disk Utility to attest the backing
file. Its input format cannot select an iPad's filesystem.

## Before a device writer

1. Establish a restore route that works when normal iOS startup fails. Preserve
   a full-storage backup for data that must survive; a designated disposable
   device can use an accepted erase-and-restore route. Verify compatible
   firmware and DFU/recovery restore access before internal-volume changes.
   Saved volume prefixes cover only their captured ranges.
2. Build an ARMv7 C or Objective-C helper for the exact iOS build. Confirm its
   ABI and privilege requirements using isolated images on that kernel before
   considering the internal mounted filesystem.
3. Qualify filesystem relocation, journal behavior and each error outcome.
   Establish how a filesystem-size result reaches the iOS partition provider.
4. Independently verify LwVM allocation and reconciliation. The fixture model's
   chunk limits are caller inputs; physical chunks need measured bounds and
   generation checks before a write plan can use them.
5. Record every durable step and test recovery after an interrupted operation.
   An uncertain call outcome requires readback and recovery before another
   mutation is considered.

The earlier 13G36 static study found a handler comparing normalized request
`0x80006802` and reading an eight-byte size. Public interface definitions encode
`0x80086802` before normalization. Later native image and physical Data tests
confirmed that userspace request on this target. A read-only minimum-size
query remains unqualified.

A later private prototype passed the native forced read-only HFS scan and
owned-image eject on 13G36. Its corrected descriptor lifecycle passed a full
repeat with a fresh 192 MiB copy and an unchanged complete-image hash.
The [validation record](validation.md#p105-native-hfs-read-only-cycle) records
the initial busy-eject failure and the qualified correction. A subsequent
read-only mount cycle also passed native extent queries over the full four-MiB
sentinel, normal unmount, filesystem checking and eject. One native image
shrink from 192 MiB to 96 MiB then passed relocation and filesystem checks,
followed by fresh backup restoration to the original size. The changed work
image remained intact. The validation record states the measured scope;
later process-stop cases are recorded below. Recovery during a kernel resize
and the LwVM update still need device tests.

A bounded native read-only snapshot has since passed both physical LwVM
header checks, repeated virtual partition tables and live HFS identity checks.
The saved files also pass independent host checksum and geometry checks.
See [the snapshot result](validation.md#p105-bounded-native-lwvm-snapshot).
The raw allocation map and native update/recovery behavior still need their
own qualification before changing the partition layout.

## Linux storage and boot

The P105 Linux milestone currently uses a host-served NFS root. The 64 GB
iPad's [reported NAND geometry](p105-nand-storage.md) differs from the
imported read-only H2FMI driver's constants. The current kernel config enables
that driver while the device descriptor still says NAND is disabled. A Linux
area needs raw-read comparison, iOS logical mapping, and a block backend that
can recover persistent writes. Startup from internal storage also needs an A5
boot-chain path.

## File protection and update recovery

The [ordinary-file tests](ios9-content-protection.md) passed fresh-process
verification before lock, during passcode lock and after unlock. The later
physical relocation test is recorded below. The raw DiskImages backend loses
the storage protection context, which limits the encryption evidence
available from image-only experiments.

The [native LwVM study and saved-file model](lwvm-update-recovery.md) now
cover header-pair ordering and failure cleanup. The study found a commit
trigger through subsequent partition I/O and a dependency on closed
descendant volumes. A native recovery RAM root has since passed USB/SSH,
unmounted reads and a supervised writer open/close. Physical update and
recovery tests remain pending.

The [native process-stop checks](ios9-process-stops.md) have since passed
both completed operation boundaries, including separate recovery and fresh
backup restoration. The protected-file cohort also passed measured
placement beyond the proposed 40 GiB boundary and fresh-process verification.
A later physical Data shrink to 40 GiB relocated all four protected files
with full content and class checks. Boot16 later passed forced read-only
fsck with Data unmounted and independently checked unchanged 40 GiB HFS
headers. After returning to iOS, a fresh process verified the 40 GiB size and
all four original protected-file contents and classes. Saved-code replay now
confirms the pair writer's modeled failure branches, while the complete
GPT/key-store commit path needs further work.

The [proposed Data/Linux layout](p105-storage-proposal.md) passes native
saved-code conversion and independent map checks. Its Linux entry spans
17,752,043,520 bytes after the proposed 40 GiB Data partition. Boot7 proved
an exact 32 MiB RAM root, its custom USB serial and SSH identity, and a mount
set containing only the RAM root and devfs. The stock kernel refused a
writable-root update. Boot9 and boot10 then started an image with a one-byte
ephemeral kernel change. Its USB serial, pinned SSH host key and build marker
matched the saved image. The RAM root remounted writable, and signed native
checks reported iPad2,5/13G36 with only `/dev/md0` and devfs mounted.

The first RAM-root storage snapshot found that unmounted System media reports
`Writable=true` in recovery. A new host-tested helper accepted that observed
value, then stopped before any flash read because opening a raw device returned
`EPERM`. Boot10 measured the same `EPERM` on all four fixed raw paths using
read-only opens. `kern.securelevel` was 0, device MAC enforcement was 1, and
a temporary request to change that setting was denied. Normal iOS reported
the same device-enforcement value. It also opened `/dev/rdisk0` with a
zero-count read command. Boot11 tested a separate kernel candidate that
masked the process vnode-enforcement bit at two credential-update sites.
The candidate booted with the pinned image identity and RAM mount set, but
read-only opens of all four raw nodes and their block counterparts returned
`EPERM`. Both diagnostics made zero device reads or writes. The denial site
remained unresolved after boot11. A matched helper opened all four raw nodes in normal iOS
using the same flags, with no device reads. A reviewed raw-access route is
required before a physical resize or LwVM update can be qualified.

Boot12 identified the MAC open-policy wrapper as the source of the refusal
using a kernel error marker. All four raw nodes returned that marker in the
verified RAM environment. Boot13 then admitted read-only opens through a
scoped rule and completed a 65,536-byte storage snapshot. System and Data
stayed unmounted. The physical LwVM headers and virtual GPT metadata matched
the earlier normal-iOS capture. A watchdog reset later ended the recovery
session. Boot14 used the traced `wdt=-1` argument and verified the watchdog
disabled at 544 and 1,452 seconds during the same RAM boot. USB and SSH worked
through that interval. Its supervised writer-open control completed one
`EPERM` refusal with a reaped child, a matching storage graph and unchanged
sampled metadata. Boot15 admitted a plain writer open on the LwVM container.
Its completed supervised test closed the descriptor, reaped the child and
verified the recreated partitions against their original identities and
ranges. All ten sampled areas remained equal. System and Data can exchange
BSD minor numbers during this recreation, so the helper binds their current
numbers to typed registry properties. Recovery after an interrupted physical
resize remains open.
The [Resize APFS parity record](resize-apfs-parity.md) tracks the
remaining service, growth and interface work. The public image lab now tests
shrink and grow-back on macOS with durable growth checkpoints.

Native iOS image growth also passed on 4 November. A fresh copy of the
captured 96 MiB HFSX filesystem grew to 192 MiB. The complete four-MiB
sentinel and its extent map passed before and after growth. Normal unmount,
forced read-only fsck and owned eject completed, followed by an exported
image whose headers and sentinel passed independent host checks. The
original seed remained read-only and hash-verified. Internal-volume growth
within the retained partition requires a device test. Growth beyond the
provider's bounds requires its larger range to be committed first.
