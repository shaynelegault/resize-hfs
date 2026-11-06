# P105 NAND geometry and Linux storage

On 3 November 2026, USB diagnostics read the `nand` registry entry from the
64 GB iPad2,5 running iOS 9.3.5 build 13G36. Its two controller records agree
with the NAND entry. A separate `diagnostics NAND` request returned
`NANDInfoFailed`; the geometry below comes from the successful registry read.
A fresh registry capture after boot15 returned to iOS on 4 November matched
every measured geometry field. Its geometry digest remains
`4efbe8d02c64e85afd686ad4958cc48be098bd0ec2ddc7f536700cd5e7e6181b`.

| Property | This iPad's iOS registry | Imported H2FMI driver |
| --- | ---: | ---: |
| Buses | 2 | 2 |
| Total chip enables | 2 | 2 |
| CE bitmap | `0x101` | `0x101` assumed |
| CAUs per chip enable | 8 | 2 |
| Blocks per CAU | 2,088 | 1,064 |
| Pages per block | 128 | 256 |
| Data bytes per page | 16,384 | 16,384 |
| Metadata bytes per page | 64 | 64 |
| Page address bits | 7 | 8 |
| Data bytes per erase block | 2,097,152 | 4,194,304 |
| Data capacity from geometry | 70,061,654,016 | 17,850,957,824 |

The registry reports twelve block-address bits and three CAU-address bits.
Each controller publishes a 16,448-byte bus page and 128 MLC pages per
block. Its SLC count is 64 pages. A logical page has 4,096 data bytes and
sixteen metadata bytes.

These figures describe iOS-reported geometry. Apple's storage stack exposes
a 64,000,000,000-byte usable logical medium. Linux raw addressing still needs
comparison with actual reads. The imported driver's `block << 8` row
calculation uses a different page-address width from this device. On this
geometry, its row for CAU 0, block 2,048, page 0 equals its row for CAU 1,
block 0, page 0: both are `0x80000`. The observed address widths instead give
`row = page | (block << 7) | (cau << 19)`. The final valid row in a CAU is
`0x413ff`, below the next CAU's first row. These calculations still need
bounded raw-page checks on the device.

A geometry-specific read-only driver would expose sixteen CAU devices. Each
has 2,088 erase blocks of 2 MiB and 4,378,853,376 data bytes. The imported
four-device inventory and 4 MiB erase size describe its reference unit.

## Existing read-side translation work

Project Cascadia's earlier [read-only `iosnand` tool](https://github.com/rzxvx/Project-Cascadia/blob/c20b85ebb951c704d7e3a664c378dde8276e3928/tools/nand/iosnand.c)
reconstructed a 16 GB unit's logical blocks from PPN page metadata. Each
4 KiB piece carried a type, write sequence and logical block address. Its
scanner selected the highest sequence for each logical address, then exposed
iOS partitions through a read-only Linux block device. That is a useful
reference for comparison with this 64 GB iPad. The tool hardcodes four CAUs,
1,064 blocks per CAU, 256 pages per block and a 16 GB logical medium.

With this unit's reported geometry, its page table, best-sequence array,
block table and logical-to-physical array would occupy about 277 MiB before
other buffers. A bounded scan for selected logical addresses can test the
metadata layout and mapping across boots without building a full in-memory
table. The active 64 GB mapping still needs physical raw-page evidence.

## Saved-file checks

Save `idevicediagnostics ioregentry nand` output privately, then run:

```sh
python3 -m lab.nand_geometry /path/to/nand.plist
python3 -m lab.nand_geometry /path/to/first-boot.plist --compare /path/to/second-boot.plist
python3 -m unittest lab.tests.test_nand_geometry -v
```

The inspector checks redundant counts and each controller's geometry.
It also calculates row shifts and boundary addresses while excluding
controller and die identifiers. A matching comparison
establishes stable reported geometry; logical mapping across boots needs
separate evidence.

## Linux inventory expectations

The imported source is
`kernel/patches/import/cascadia/0016-mtd-Add-the-Apple-H2FMI-NAND-controller.patch`.
The current `kernel/configs/apple-armv7/config` sets
`CONFIG_MTD_APPLE_H2FMI=y`. The P105 descriptor's NAND-disabled comment is
stale for this source configuration. Historical zero-MTD observations belong
to their recorded builds.

Capture the running kernel config and DeviceTree with `/proc/mtd` and each
MTD device's sysfs geometry and flags. The imported driver sets
`MTD_NO_ERASE` and omits `MTD_WRITEABLE`; check those restrictions. Its
reference geometry remains unsuitable for this unit. The config alone
cannot establish that the running DeviceTree enabled the controller.

## Contract required before Linux writes

The [proposed Linux area](p105-storage-proposal.md) occupies LwVM chunks
682 through 946 in the iOS logical provider. Mapping that area onto NAND
requires the provider's translation and metadata. A released LwVM range
cannot be treated as a contiguous raw-MTD range.

Read tests must compare bounded raw samples with the iOS logical view,
using the observed geometry. Preserve metadata and record retired-block
and refresh statuses, then repeat after a boot to check mapping stability.
The normal-iOS and RAM-recovery diagnostics observed opposite BSD minor
numbers for System and Data while their path names stayed the same. A
cross-boot comparison must use the media registry, partition identifiers and
bounded content checks, rather than assuming a stable device minor.

A writable backend must keep its metadata outside iOS-owned space and
define a durable commit. Fault tests must interrupt data programming,
erase operations and mapping updates. Recovery must select a committed
mapping while handling torn updates and bad blocks. Block flushes must
reach that durable boundary before ext4 is tested above the backend.

The native key-store ordering and discard-array findings remain open in
the [LwVM recovery study](lwvm-update-recovery.md). Boot13 admitted read-only
opens of four logical raw-device nodes in RAM recovery, then checked bounded
LwVM, GPT and HFS metadata with System and Data unmounted. Both LwVM headers
and all four GPT metadata blocks matched the earlier iOS capture. These reads
use Apple's logical storage stack. Raw NAND page comparisons and a writable
Linux mapping remain pending. Boot14 kept USB/SSH access through 24 minutes
with the watchdog disabled. Its supervised writer-open control completed
one permission refusal with unchanged sampled metadata. Boot15 completed
an accepted writer open and close through Apple's LwVM stack, including
partition recreation and equal sampled metadata. A writable Linux backend
and physical partition-update recovery remain pending.


The physical Data filesystem has since shrunk to 40 GiB through Apple's
native storage stack. Boot16 passed unmounted read-only fsck, and the four
protected test files retained their contents after returning to iOS. The
Data partition still spans 60,701,716,480 bytes, and Linux has no allocated
partition. Raw NAND addressing and persistent Linux writes remain unqualified.
