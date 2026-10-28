# resize-hfs

Tools for investigating HFS+ and HFSX storage on older Apple devices. This
project lives at [shaynelegault/resize-hfs](https://github.com/shaynelegault/resize-hfs).
It grew from the iPad mini 1 Wi-Fi work for OrchardLinux and may be contributed
to OrchardLinux as its device support develops.

The Swift commands inspect saved regular files. A separate macOS lab tests
filesystem shrinking on newly created, disposable disk images. Work toward
an iOS 9 resize helper is tracked in [the device roadmap](docs/ios9-roadmap.md).

## Saved-file inspection

Requires Swift 5.9 or later on macOS or Linux.

```sh
swift test -j 2
swift run -j 2 resize-inspect /path/to/saved-volume-prefix.bin
swift run -j 2 inspect-hfs-image /path/to/saved-raw-volume-image.hfs
swift run -j 2 inspect-gpt-header /path/to/saved-header-block.bin 4096
swift run -j 2 inspect-lwvm-header /path/to/saved-lwvm-header.bin
swift run -j 2 inspect-revision1-fixture \
  primary-header.bin primary-entries.bin backup-header.bin backup-entries.bin \
  4096 MEDIA_BLOCK_COUNT
```

`resize-inspect` reads the primary HFS+ or HFSX header at byte 1024. It reports
aggregate geometry and attribute bits, including the journal and content
protection flags. A saved prefix can be enough for this inspection; the
result alone cannot establish that a full backup exists.

`inspect-hfs-image` requires the complete declared volume in its saved file and
checks the primary and filesystem-end alternate header geometry. A larger
backing file can contain a smaller filesystem after a filesystem-only shrink.
Its result covers the selected headers; filesystem checking remains separate.

`inspect-gpt-header` checks one saved header block and reports its raw revision.
The observed LwVM-facing revision value `0x00000001` is distinct from UEFI GPT
revision 1.0 (`0x00010000`). `inspect-revision1-fixture` checks the selected
header geometry, CRCs, mirrored entry arrays and used ranges from four saved
files. It emits aggregate values without partition names or GUIDs.

`inspect-lwvm-header` reads one saved 4 KiB LwVM header and checks its CRC
using the inspected iOS 9.3.5/13G36 contract. It reports the raw media size and
partition count. The allocation map, partition entries and backup header
remain unchecked. See [the header diagnostic](docs/lwvm-header.md).

The library retains in-memory shrink geometry and LwVM reconciliation fixtures.
Their inputs are invented maps and explicit caller-supplied bounds. Those
models provide no mapping from a device's partition view to physical LwVM
chunks. The executable inspectors open regular files read-only, reject device
files and final-component symlinks, and check file identity during reads.

## Image experiments

The macOS lab binds every filesystem operation to a newly created disk image.
It checks the image's backing relationship before each mutation and keeps a
verified copy for restore tests. Its evidence covers the host's HFS driver.
The iPad's iOS 9 ABI and LwVM behavior need separate device qualification.

See [the image lab](docs/image-lab.md) for the command and current results.
Generated images and operation receipts stay outside Git.

## Device scope

The first research target is the original iPad mini Wi-Fi (`iPad2,5`, P105AP),
running iOS 9.3.5 build 13G36 with HFSX and LwVM. Native on-device resizing,
LwVM writes and recovery after an interrupted device operation remain open.
A free-block count in an HFS header cannot determine a safe shrink target.

The OrchardLinux P105 desktop currently runs from a host-served NFS root.
Storage preparation and a writable Linux flash path require their own work;
releasing space alone cannot provide an untethered Linux boot.

## License and source

Original project code is MIT licensed. [Source notes](docs/provenance.md)
record the imported research and external format references. Apple firmware,
kernel captures, calibration, raw device data and credentials stay private.

## P105 file protection and recovery research

Native tests now record file-class access across passcode lock and unlock
on iOS 9.3.5. [The results](docs/ios9-content-protection.md) state the
measured scope and the remaining content-protected relocation work.
An original [LwVM recovery model](docs/lwvm-update-recovery.md) adds eighteen
saved-file tests for the traced header-pair and chunk rules. A physical
partition update still needs native recovery and provider qualification.

Native P105 [process-stop and restore checks](docs/ios9-process-stops.md)
now cover exits before a resize request and after its successful return on
disposable iOS HFSX images. Four protected files also passed measured
placement beyond the proposed 40 GiB boundary and fresh-process verification.
Their physical relocation and the LwVM commit path remain under qualification.
