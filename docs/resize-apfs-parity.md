# Resize APFS parity target

The comparison uses OrchardLinux/resize-apfs at
[`ac1658923378dcb800523d7dcd45002fc2bc5862`](https://github.com/OrchardLinux/resize-apfs/tree/ac1658923378dcb800523d7dcd45002fc2bc5862),
checked against the upstream head on 4 November 2026. The first HFS device
target is the 64 GB iPad mini Wi-Fi, iPad2,5/P105AP, on iOS 9.3.5/13G36.

Resize APFS lets the owner choose a size, review the change and follow a
privileged operation across app restarts. The service coordinates filesystem
and partition changes, checks the result and offers an unformatted Linux
partition. Its README records hardware-tested APFS shrinking and growing on
J71b with iPadOS 17.7.11; Linux partition creation remains unverified there.

| Capability | HFS evidence | Work needed on P105 |
| --- | --- | --- |
| Inspect storage and select a target | Saved inspectors; bounded native reads in iOS and RAM recovery; matching LwVM/GPT metadata across those boots; measured 40 GiB Data proposal | Establish a supported minimum and expose supported targets |
| Shrink the filesystem | One physical Data shrink to 40 GiB relocated four protected files with full content checks; unmounted native fsck and independent HFS readback passed; a fresh iOS process verified the same files and 40 GiB size after reboot | Qualify recovery from an interrupted physical resize and supported target sizes |
| Grow the filesystem | Native iOS image growth from 96 MiB to 192 MiB, with full sentinel checks, fsck and independent host readback; host stop/restore checks | Qualify provider expansion before filesystem growth on internal storage |
| Resize the partition and optionally allocate Linux | Saved native conversion accepts the 40 GiB Data proposal and 17,752,043,520-byte Linux entry | Qualify key retention, discard controls, header writes and readback through the native LwVM provider |
| Keep operation status across disconnects | Durable image-lab records and one-use device research runners preserve uncertain outcomes | Build the shared operation service, persist its receipts beyond RAM recovery and reconnect the UI to the same operation |
| Launch and present a device utility | ARMv7 helpers and a verified USB/SSH RAM recovery boot | Package the A5 boot path and an iOS 9 interface with review, progress and recovery screens |

The operation order follows the storage dependency. A shrink must verify the
reduced HFS filesystem before releasing its partition space. Growth requires
the larger backing partition to be committed and read back first. LwVM can
change the encryption-key store before header I/O, so recovery must account
for both stores. The [LwVM study](lwvm-update-recovery.md) records that ordering
and the discard-array defect, together with host-tested candidate controls.

An interrupted call remains unresolved until fresh evidence establishes what
happened. A successful native return also requires independent readback before
the utility reports completion. Existing free-block counts supply usage
information; they do not establish a safe minimum for protected-file relocation.

Boot14 repeated bounded raw reads with System and Data unmounted, using the
same scoped read-only kernel as boot13. The partition metadata matched the
earlier captures. A volatile `wdt=-1` argument disabled the watchdog, which a
typed registry query verified at 544 and 1,452 seconds within the same boot.
USB and SSH stayed accessible through that interval.

The supervised writer-open control then completed one `O_RDWR` attempt with
`EPERM`. Its child exited and was reaped, the storage graph matched, and all
sampled metadata remained equal. The test exposed and fixed a decoder bug
that rejected valid high-bit device identifiers. Boot15 subsequently passed
an accepted writer open and close with System and Data unmounted. It verified
the recreated partitions and all ten pre/post metadata samples. Boot16 later
checked the physically shrunk 40 GiB Data filesystem with System and Data
unmounted, then returned to iOS for a fresh full-content check of the four
protected test files. Interrupted physical resize recovery and LwVM commit
recovery still need device tests.

Linux installation and persistent NAND writes continue as a separate part
of OrchardLinux. Resize parity ends with a verified storage layout. The
[NAND work](p105-nand-storage.md) must supply the block device that Linux uses
within its allocated area.
