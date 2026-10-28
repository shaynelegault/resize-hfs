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
