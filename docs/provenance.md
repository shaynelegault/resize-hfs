# Source and license notes

The initial `ResizeCore`, three saved-file commands and 33 synthetic tests
were written in the author's local legacy iOS storage research. A preserved
copy supplied this standalone project on 28 October 2026. Original source
bytes still match that copy. `source-import.json` records the public Swift
source hashes before the MIT headers and new work were added.

This repository adds a complete saved-image header check and a separate
macOS image experiment. Its original code is licensed under MIT. System
headers and frameworks come from the user's installed SDK and operating
system during compilation and execution.

## Format and interface references

- [Apple HFS Plus Volume Format, TN1150](https://developer.apple.com/library/archive/technotes/tn/tn1150.html)
  describes the volume headers, allocation blocks and byte order.
- [Apple HFS format definitions](https://github.com/apple-oss-distributions/hfs/blob/main/core/hfs_format.h)
  provide names for raw journal and content-protection flags.
- [UEFI GPT format](https://uefi.org/specs/UEFI/2.10/05_GUID_Partition_Table_Format.html)
  describes the standard field offsets and CRC rules. The fixture tools keep
  the observed raw revision value 1 separate from standard revision 1.0.
- [Apple's HFS resize implementation](https://github.com/apple-oss-distributions/hfs/blob/main/core/hfs_resize.c)
  and [control definitions](https://github.com/apple-oss-distributions/hfs/blob/main/core/hfs_fsctl.h)
  informed the disposable macOS experiment. These are APSL-2.0 references;
  their source implementations are external to this repository.

`lab/image_fsctl.c` computes the interface request with the installed SDK's
`_IOW('h', 2, uint64_t)` and checks its value at compile time. It calls the
host filesystem through `ffsctl`, then obtains extent observations through
`F_LOG2PHYS_EXT`. The lab's own backing checks surround that call.

The GPL projects [danzatt/hfs_resize](https://github.com/danzatt/hfs_resize)
and [openiBoot](https://github.com/iDroid-Project/openiBoot) remain research
references. Their implementations are outside this source tree. OrchardLinux's
[MIT-licensed resize-apfs](https://github.com/OrchardLinux/resize-apfs) provided
an example of separating core code, commands and tests; APFS implementation
code was not imported.

## Fixture model boundary

The LwVM model uses caller-invented 1,024-entry maps and explicit limits. The
original workspace's static 13G36 study informed its owner/index masks and
exact `0xf111` marker rule. Additional model rules require unique contiguous
indices. That fixture policy has no established equivalence to a live device
map or the iOS partition provider's update behavior.

Kernel captures and the private static-analysis trace remain outside this
repository. The model serves arithmetic tests while live LwVM preparation
awaits an independently qualified format and recovery procedure.

## Saved LwVM header checksum

The saved-header diagnostic implements the checksum contract observed in an
offline trace of build 13G36. [Its scope](lwvm-header.md) records the fields,
trace anchors and component hash. The existing original CRC32 function is
reused. New fixtures use independently computed Python zlib checksums;
device data and Apple implementation bytes remain outside this repository.

## Header-pair recovery model

`lab/lwvm_recovery/saved_pair_model.py` and its eighteen tests are original
MIT code derived from the saved 13G36 study. They use invented metadata
windows and explicit discard policies. The [research note](lwvm-update-recovery.md)
records component hashes and trace anchors. Native code and device captures
remain private.

## Key-store ordering model

`lab/lwvm_recovery/key_commit_model.py` and its twelve tests are original
MIT code. The model follows the traced key-store-before-header order and
uses fixed invented identities, keys and prefixes. Its AES operation is
an identity mock. The separate header model supplies regular-file failure
and restoration cases; firmware bytes and native key material remain
outside this source tree.
