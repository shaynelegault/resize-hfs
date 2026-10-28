# Saved LwVM header diagnostic

`inspect-lwvm-header SAVED_HEADER_OR_IMAGE` reads the first 4096 bytes of a
saved regular file. It uses the same read-only, final-component symlink
refusal and file-identity checks as the other inspectors.

The inspected iOS 9.3.5 build 13G36 recognizes two 16-byte signatures. For the
CRC-bearing signature, the driver clears bytes 0x2c through 0x2f and computes
CRC32 across the full 4096 bytes with seed 0, then stores the result little
endian. The diagnostic applies that contract to a copy in memory. Its tests
use a checksum computed independently with Python zlib and corrupt the last
byte to exercise the complete bound.

The alternate recognized signature carries no checksum requirement. The
command reports `checksum_matches: null` for it. A damaged CRC-bearing
header yields `checksum_matches: false`; as with `inspect-gpt-header`, this
diagnostic reports the observation without converting it into a valid layout.

The diagnostic reports the raw media size at 0x20 and partition count at 0x28.
Its accepted envelope requires a positive media size aligned to 4096 bytes and
between 1 and 8 partitions. The native 13G36 header validator checks a maximum
of 8. Older research readers that allowed 12 do not define this tool's scope.

An accepted header leaves its partition entries and all 1024 allocation words
unchecked. The command performs no chunk allocation, free-space calculation,
header-pair selection or update. Every result includes
`physical_allocation_validated: false`, `header_pair_validated: false` and
`resize_supported: false`.

The saved build's generator is at 0x80c469d0; its validator preserves the
original checksum and compares the generated value at 0x80c46992. The call
stub at 0x80c4faac resolves to the saved kernel's exported crc32 routine.
These facts came from an offline trace of the author's private build 13G36
kernel capture. Original implementation bytes and device headers remain
outside this repository. The extracted component's SHA256 is
`a0c0d1392fbf42a45d97d78189c6121d9a7231ed15341b080f3100d307c4e9f9`.

The native read-only snapshot's primary and backup headers independently
passed this diagnostic, with matching Python zlib results. Its full capture
and pair comparison remain private. This single-header command continues to
report `header_pair_validated: false` for each input.

Native table reads use block-aligned lengths. The separate
`inspect-revision1-fixture` command requires entry-array files to contain
exactly `entry_count * entry_bytes` bytes. For the measured two-entry view,
that is 256 bytes inside the 4 KiB table capture. Host validation used separate
logical-array copies and preserved the original aligned captures.
