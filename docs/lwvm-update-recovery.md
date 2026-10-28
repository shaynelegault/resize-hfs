# P105 LwVM update and recovery research

This note records the offline study of iPad2,5 kernel build 13G36 and the
original saved-file model in `lab/lwvm_recovery/saved_pair_model.py`.
The model creates fresh regular files containing invented metadata.
Its tests exercise selected rules traced in the native driver.

## Native path under study

LwVMMedia exposes a synthetic GPT view. The traced write path stages the
primary header and entry-array windows, then commits the proposal on later
partition I/O. A read within the first partition reaches that commit path.
An ordinary writable open requires descendant storage drivers to close.
Normal iOS keeps System and Data mounted. A recovery image with a RAM root
is being qualified for further native work.

The observed medium has 4,096-byte preferred blocks and a 64 MiB chunk.
The physical headers sit at byte 0 and byte 67,104,768. The native pair writer
calculates the CRC, writes the primary, then writes the backup. Each write
is followed by a synchronize request and full-block readback. The traced
routine discards the synchronize return value.

On success, the writer requests unmap of the space between the two header
blocks. A write or readback failure requests unmap of the entire first
chunk, including both headers. The routine retains its pair result while
discarding the unmap return value. Provider and flash effects require a
device test.

The read/CRC layer selects a valid primary without comparing the backup.
If the primary fails and the backup passes, it calls the pair writer to
repair both copies. It then reports read success even when that repair
writer returned failure. The selected buffer can therefore remain available
in memory while the stored pair depends on the failure cleanup's effects.

These observations come from saved native code. They leave BSD write
acceptance and durable recovery unqualified. Encryption-key operations and
the later trim of released partition chunks also need their own evidence.
Restoring a header preimage cannot restore partition data that was discarded.

## Saved-file model

Run the focused suite from the repository root:

```sh
python3 -m unittest lab.tests.test_lwvm_pair_recovery -v
```

Eighteen tests cover the modeled statement boundaries and CRC selection.
They include a torn primary, different valid copies, failed backup writes
and fallback repair failure. Separate assertions cover trailing chunk
release, allocation from exact `0xf111` cells and the slots selected for
post-update unmap.

Each case owns a fresh 65,536-byte metadata window. Its invented header
declares a 64 MiB medium, which yields a 64 KiB chunk under the studied
formula. The file contains only that metadata window. Markers A and B
distinguish fixture contents through an opaque field.

The model's `keep` and `poison` policies make the unknown discard effect
explicit. One leaves requested bytes intact; the other replaces them with
a fixed byte pattern. A saved preimage can be copied into a fresh regular
file while the damaged work file retains its hash. This establishes the
model's file behavior. Native flash ordering, power loss and recovery remain
open, as recorded by the model's qualification fields.

## Trace provenance

The studied LightweightVolumeManager component has SHA-256
`a0c0d1392fbf42a45d97d78189c6121d9a7231ed15341b080f3100d307c4e9f9`
inside the 13G36 kernel whose SHA-256 is
`8eae16f060a71d4f3790385951588f8198d0f21cdb74146f9750941a3d764125`.
The pair writer begins at `0x80c48958`; the fallback read routine begins
at `0x80c49a68`. GPT staging reaches `0x80c4b764`, followed by lazy commit
at `0x80c4b854`. Chunk reconciliation and post-update unmap begin at
`0x80c4d3e0` and `0x80c4d66c`.

The model and tests were written for this project under MIT. Firmware bytes,
device headers and the full private trace stay outside the repository.
Apple's [IOStorage interface](https://github.com/apple-oss-distributions/IOStorageFamily/blob/IOStorageFamily-191/IOStorage.h)
and [IOMedia open handling](https://github.com/apple-oss-distributions/IOStorageFamily/blob/IOStorageFamily-191/IOMedia.cpp)
supplied the public interface contracts used in the study.

## Replay of the saved ARMv7 routines

A private host harness also executed the exact saved Thumb code for the
13G36 pair writer, fallback reader and their read/write helpers. Both CRC
wrappers ran with the kernel's original CRC routine and table. The provider
and descriptor lifetime calls used declared memory mocks. Executable pages
stayed read-only, and each entry had bounded memory access and an instruction
limit.

Seventeen test methods covered 58 emulated cases and executed 3,207,552
guest instructions. Ten cases agreed with the independently written model
on return status, final provider bytes and requested unmap ranges. The runs
confirmed that synchronize and unmap errors can be discarded, and that a
fallback read can return success after repair has failed. A failed CRC
comparison also leaves a recomputed CRC in the RAM buffer while returning
an error, so the status must accompany those bytes.

The emulator uses synthetic metadata windows. Its mocked provider cannot
establish flash persistence or the effect of a real discard request.
Firmware input bytes and captured device metadata remain private.

## An unchanged proposal reaches the key store

The saved GPT conversion path retains encrypted partition keys when the
partition identities match. Those keys enter a pending list even when the
sizes and attributes remain equal. With the traced effaceable-storage
policy enabled, the commit path can write that list before calling the
physical header-pair writer. Its envelope receives a fresh 12-byte random
prefix. A matching geometry therefore still needs a key-store recovery
contract.

The observed unchanged map retains all 946 occupied partition chunks.
After a successful commit, the driver still requests discard for the six
already-free chunks, totaling 402,653,184 bytes. Pair-write failure has the
separate first-chunk cleanup described above. The checked caller shows no
rollback of an earlier key-store update after a later pair failure.

The complete GPT conversion and key-store path still needs an executable
fault model. Native qualification first needs a verified RAM root with
closed System/Data descendants, followed by a bounded writer open and
close with fresh metadata checks. The physical metadata writer remains
unimplemented while that work proceeds.

## Key-store ordering fixture

`lab/lwvm_recovery/key_commit_model.py` supplies a memory-only model for one
unchanged retained-key proposal. Its fixed invented disk and partition
identities accompany one synthetic 32-byte key. Two 12-byte prefixes
distinguish the old and proposed logical envelopes. The AES boundary uses
an identity mock; the model implements no encryption or native key access.

Twelve tests cover missing retained keys, capacity and AES failures, then
the key-store call's returned status. A store error has an explicit `keep`,
`replace` or `poison` policy because its physical partial-write behavior
remains unknown. Those failures stop the pair callback. The success path
requires the updated key store to be visible when that callback begins.

The existing regular-file pair model supplies header failures and preimage
restoration. Tests preserve a changed key store after a failed pair update,
and show that restoring the header preimage leaves that store unchanged.
Another case stops after the key-store call while both headers retain
their original bytes. A callback exception or ambiguous non-boolean result
preserves the uncertain state and consumes the fixture's one attempt.

A private mutation that moves the pair call ahead of the key-store update
fails the ordering tests. The unmodified source passes all twelve cases;
full Python lab discovery now passes 50 tests. Run the focused suite with:

```sh
python3 -m unittest lab.tests.test_lwvm_key_commit -v
```

The fixture retains false qualification flags for native key persistence,
encryption and power loss. Actual store capacity/error handling and later
header failure were also studied in saved-code replay, whose provider and
cryptographic resources remain mocked.

## Full saved-code commit and discard array

The next private harness executed the saved pending-GPT commit against the
captured unchanged proposal. It reached the native parser and reconstructed
the complete original 4 KiB header. All 946 occupied map cells retained
their bytes. Synthetic cpx objects supplied the retained key, and declared
mocks handled AES and the external key store. Child-media rebuilding also
used a checked mock.

Eight cases passed 79 assertions. Capacity error, insufficient capacity,
AES failure and a returned store error each stopped header-provider I/O.
An unavailable retained key stopped the store as well. The injected primary
and backup write failures occurred after the modeled key-store success;
each reached the whole-first-chunk cleanup request. Native key loading and
store persistence remain outside those mocks.

The successful case refined the earlier free-run footprint calculation.
The saved code initializes one 16-byte extent for the six free chunks, with
the range described above. At the provider call it supplies an extent count
of six. That count exposes five additional entries from its stack.

The harness then executed the exact saved `IOMedia::unmap` validator and its
`IOService::isInactive` check. In this fixture the second entry exceeds the
64 GB medium. The validator returned `0xe00002c2` (`BadArgument`) before
calling the driver. LwVM discarded that status and returned success. Its
separate header-gap request supplied count one and reached the mocked
driver.

The first stopped run's 96-byte array remains preserved beside the completed
replay. An independent run reproduced the same result after checking all
47 input pins. It executed 9,324,927 instructions and preserved the header
and occupied map. A different native stack can supply different extra
entries, so physical discard effects still need qualification.

This result adds a provider-array failure case to the physical update plan.
The writer needs a complete account of that array and the key-store state
before its first device mutation. Native writable-open admission and child
rematching remain separate runtime tests.
