# P105 Data and Linux layout proposal

The saved 13G36 code accepted this proposed layout in the host emulator for
the measured 64 GB iPad2,5 profile. Its inputs preserve the existing System
entry and Data identity. The added Linux entry uses the standard Linux
filesystem type GUID with its encryption attribute clear.

| Area | Proposed bytes | Assigned 64 MiB chunks |
| --- | ---: | ---: |
| System | 2,716,160,000 | 41 |
| Data | 42,949,672,960 | 640 |
| Linux | 17,752,043,520 | 265 |

The proposed Linux range ends at the original Data partition's end.
The saved native converter produced the expected complete map: System
retains physical chunks 1–41 and Data retains 42–681. Linux receives
682–946. The six previously free chunks remain free. Every partition's
logical indices are complete, and independent checks match its converted
type, identity, name and bounds to the proposed GPT entry.

A fresh independent CPU reproduced the result after checking all 47 frozen
origin pins. The candidate header passed its CRC check. The replay executed
9,336,644 instructions with synthetic keys and declared provider mocks.

Nine host cases passed 123 assertions. A duplicate identity, overlapping
ranges and an out-of-bounds proposal each returned an error before header
writes. Missing-key and key-store failures also retained the original pair.
The injected backup-write failure left a valid proposed primary beside a
valid original backup while the active RAM header stayed original. Its
modeled key store had already changed, which makes the recovery state
depend on both stores.

The discard-array issue from the [full commit study](lwvm-update-recovery.md#full-saved-code-commit-and-discard-array)
also appears here. The first initialized extent covers 271 chunks, including
the proposed Linux area and the six free chunks. The caller supplies 271
array entries while initializing one. Instrumentation captures six entries
without changing guest registers or bytes. The exact native validator
rejects the second entry in this fixture and LwVM returns success afterward.
Different stack contents and physical discard effects remain unqualified.

On 4 November 2026, one native request shrank the physical Data filesystem
to 42,949,672,960 bytes. Four protected test files moved below the new
boundary with their content and protection classes intact. Independent reads
confirmed that size in the primary HFS header and both alternate locations.
Data's partition remains 60,701,716,480 bytes, and both LwVM headers match
the saved preimages. Linux has no allocated partition yet.

The [physical shrink record](validation.md#p105-physical-data-shrink) includes
forced read-only fsck in a later RAM boot and a fresh protected-file check
after returning to iOS. The filesystem retained its 40 GiB size. Recovery
after an interrupted physical resize remains open. The
proposed partition conversion still needs native commit and recovery tests.
A writable Linux block backend and startup without the host have their own
qualification work.

The [NAND storage study](p105-nand-storage.md) records this unit's measured
iOS registry geometry and its differences from the imported Linux driver.
