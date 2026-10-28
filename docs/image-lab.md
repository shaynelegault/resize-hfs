# Disposable HFSX image lab

The lab creates a fresh 192 MiB raw HFSX image on macOS and asks the host HFS
driver to shrink its filesystem to 96 MiB. Its backing medium keeps the
original size. All mutations stay inside the image created by that run.

Requires macOS, Python 3.9 or later, and Xcode Command Line Tools. The helper
builds locally against the installed SDK. The lab accepts a new output
directory and supplies its own fixture; there is no arbitrary-device option.

```sh
python3 lab/image_lab.py run --output /private/tmp/resize-hfs-example
python3 lab/image_lab.py restore \
  --run-dir /private/tmp/resize-hfs-example \
  --output /private/tmp/resize-hfs-restored
```

Choose output paths that do not exist. Keep the output directories while
reviewing an interrupted experiment. The original backup remains available
when a result is uncertain.

## What it checks

The fixture starts with a filler file that pushes a four-MiB sentinel beyond
the planned filesystem end. The filler is removed, and the image is detached
before its verified whole-file backup is copied. The experiment checks that
the sentinel's extents cross the boundary before calling the resize interface.

Python and the native helper independently validate the image's canonical
path, inode, ownership and attachment. The helper also requires the exact
mounted virtual disk, private fixture token and expected sizes. A root
directory descriptor binds its `ffsctl` call to that checked filesystem.
Physical media, partitions, a changed mount and mismatched image evidence
are refused by these checks. The fixed experiment shrinks only `fixture.dmg`.

The host's `IOKitSize` records backing-medium size. `VolumeSize` and `TotalSize`
report the reduced filesystem after a shrink on the tested host. The lab uses
the backing field and the image's block count for its media check, then reads
the mounted filesystem's size separately.

After the call, `F_LOG2PHYS_EXT` must report the sentinel below the new end.
Its complete content hash must agree. The lab detaches and reattaches the
image read-only, checks both HFS header geometries, verifies the sentinel and
runs `diskutil verifyVolume`. Verification must perform the filesystem checks
and report success. The backing image's hash must remain unchanged throughout
that read-only session.

The restore command validates the original backup's hash against a durable
checkpoint and copies it into a fresh image. It then repeats read-only mount,
sentinel and filesystem checks, including the original filesystem size.

## Interruption checkpoints

```sh
python3 lab/image_lab.py run \
  --output /private/tmp/resize-hfs-stopped \
  --stop-after shrink-returned
python3 lab/image_lab.py restore \
  --run-dir /private/tmp/resize-hfs-stopped \
  --output /private/tmp/resize-hfs-recovered
```

`--stop-after` accepts `backup-verified`, `shrink-requested` and
`shrink-returned`, returning exit 42 after the chosen durable record. Each
journal line contains its sequence and previous-record hash. Recovery can
use the complete prefix of a torn final record and requires an already
verified backup. The original mutation is never replayed.

These stops exercise the supervisor's checkpoints. They leave kernel-level
power loss during `ffsctl` and real iOS/LwVM recovery for later tests.

## Evidence

Each run retains a private operation journal, whole-image backup receipt,
native binding receipts and filesystem-check output. `result.json` records
the observed sizes and scope. The images and receipts are excluded from Git.
See [validation](validation.md) for the tested host and measured results.
