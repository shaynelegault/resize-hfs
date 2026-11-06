# P105 content-protection file tests

On 28 October 2026 a private ARMv7 helper tested ordinary files on the
content-protected Data volume of iPad2,5 running iOS 9.3.5 build 13G36.
It created four 64 KiB files in a fresh directory. Each empty file received
its protection class through native `fcntl` before payload bytes were
written and synced. A saved manifest bound subsequent checks to those
same file identities and complete payload hashes.

The helper used the native ARMv7 interfaces: commands 63/64 for the file
class, command 77 for the filesystem protection format version and command
65 with its guarded 20-byte extent structure. The observed filesystem
format version was 5. That value describes the format; lock state requires
separate evidence.

The first cohort used the owner's original setup without a passcode.
All four files remained readable with their original classes and hashes
after the owner turned off the screen.

The owner then set a temporary passcode directly on the iPad. A fresh cohort
passed creation and verification in another process while unlocked.
After the owner locked the iPad and waited 15 seconds, a new process tested
access again. A final process repeated verification after the owner entered
the passcode on the iPad.

| Class | Passcode locked | After unlock |
| --- | --- | --- |
| A, value 1 | Open refused with `EPERM` | Full bytes and class matched |
| B, value 2 | Open refused with `EPERM` | Full bytes and class matched |
| C, value 3 | Full bytes and class matched | Full bytes and class matched |
| D, value 4 | Full bytes and class matched | Full bytes and class matched |

The probe queried file access through the filesystem. Its report retains
`keybag_lock_proven=false` because it made no keybag-state request. The
owner removed the temporary passcode after these checks.

The source passed 187 host checks under address and undefined-behavior
sanitizers. Those tests mock native calls, while an independent reader
checks the emitted JSON and four payload hashes. The actual ARMv7 binary
had 27 imports, linked only libSystem and carried zero lazy-binding entries.
Its signed no-argument launch preceded the active file tests. Target SSH
identity, signing artifacts and manifests remain private.

## Scope of the file-access tests

These results qualify file access for the observed lock and unlock states.
Those tests issued no resize request. The later physical relocation test
below checks full payloads and classes across the native operation.

The studied raw DiskImages backend drops the storage attributes that carry
the protection context before its image-file write. A protected filesystem
header on that backend can exercise filesystem branches while the inner
payload reaches the backing file in plaintext. That backend cannot establish
the encryption behavior of physical Data relocation.

Later RAM recovery boots established access with System and Data unmounted.
Boot16 checked the reduced filesystem read-only. Mounting protected Data in
recovery and recovering from interrupted physical operations still need
separate tests.

The ABI study used Apple's versioned
[fcntl definitions](https://github.com/apple-oss-distributions/xnu/blob/xnu-3248.60.10/bsd/sys/fcntl.h),
[protection-class definitions](https://github.com/apple-oss-distributions/xnu/blob/xnu-3248.60.10/bsd/sys/cprotect.h)
and the HFS relocation source. The test helper is original project code;
Apple implementation bytes and captured device data stay private.

## Protected files beyond the proposed boundary

A fresh native cohort then placed one 64 KiB file of each class beyond
40 GiB on the unchanged Data filesystem. Each file received one
`F_PREALLOCATE` request through the checked ARMv7 32-byte structure, using
the volume-position hint. The helper accepted the result only after
checking the returned allocation size, immutable request fields and
surrounding guard bytes. Complete extent queries measured the placement.

All four requests succeeded. Every file occupied one disjoint, aligned
extent beyond 42,949,672,960 bytes and inside the original Data size.
After writing and syncing the payloads, the helper closed and reopened
each file. The observed class, full hash and 64 KiB allocation matched.
A new process repeated those checks from the saved manifest and issued
zero allocation requests. The owner had removed the temporary passcode
before this cohort ran.

The helper's host suite passed 1,465 sanitizer checks. A manifest guard
refuses an unexpected file type, size or owner before opening the leaf;
descriptor identity and timestamps must then match before reading. Its
actual ARMv7 binary retained 27 imports and zero lazy-binding entries.

These placement tests issued no shrink request. A later cohort used a
persistent directory directly below `/private/var`, which survived a normal
reboot before the physical shrink described below.


## Physical relocation and a later boot

On 4 November 2026, one native Data resize reduced the filesystem from
60,701,716,480 bytes to 42,949,672,960 bytes. The four persistent class A/B/C/D
test files moved from measured extents above 40 GiB to extents near 1.879 GB.
Their complete contents, classes, inodes and timestamps passed the native
postchecks. The owner had removed the temporary passcode before this cohort.

Boot16 then checked Data with `fsck_hfs -f -n` while System and Data were
unmounted. The checker reported Data was OK. After returning to normal iOS,
a fresh process reopened all four files and verified their original complete
hashes and classes below the retained 40 GiB boundary. The Data partition
kept its original size throughout. [The validation record](validation.md#p105-return-to-ios-after-the-physical-shrink)
describes the checker and the retained host-export failure.

This result covers the controlled four-file cohort and the completed resize.
Interrupted physical operations and passcode-locked relocation need their own
qualification. Linux flash writes remain outside this test's scope.
