# P105 native HFS process-stop checks

The private ARMv7 image lab now covers a process exit immediately before a
resize request and an exit after that request returns success. These runs
use the native iOS 9.3.5/13G36 HFS driver on iPad2,5. Each case starts from
a fresh 192 MiB HFSX image copied from the same verified original. The
proposed filesystem size is 96 MiB; the image's virtual medium stays 192 MiB.

A producer freezes its journal and emits a canonical handoff ticket before
exiting. The ticket binds the work image, mounted filesystem and registry
objects to the prepared manifest. A different executable then checks the
ticket against the retained objects. Recovery verifies all four MiB of the
sentinel, closes mounted descriptors and performs a normal unmount. The
native forced read-only filesystem scan must finish before a fresh raw
descriptor can authorize the single owned eject.

The before-request case retained the original filesystem geometry and
sentinel map. In the after-return case, the single resize call returned zero.
Recovery found the reduced geometry and all sentinel extents below 96 MiB,
with the complete original payload hash. Both cases passed unmount,
filesystem checking and eject while preserving the original media inventory.

## Failures retained during qualification

The first before-request producer stopped at its intended boundary, then
failed to serialize its ticket. Its registry snapshot reset the entry count
while leaving unused array slots uninitialized. The canonical encoder
refused those bytes. A separate helper bound that failed instance, checked
the unchanged image and completed its normal unmount and eject. The empty
ticket and original failure journal remain preserved. Zero resize requests
ran in that failed case.

A fresh revision clears the entire snapshot. Its regression tests poison
the output storage before exercising empty and populated registry walks,
then encode and decode their actual results. Restoring the original
count-only initializer in a private mutation copy makes those tests fail.
The corrected before-request case completed recovery and a fresh restore
from the original backup, with full read-only checks at the original size.

The next after-return attempt issued one successful resize but failed before
finishing its ticket. Its mount-table query used `MNT_NOWAIT`, which still
reported the original block count. A separately reviewed recovery measured
49,152 cached blocks, then 24,576 through `fstatfs` on the bound mount. The
cached query subsequently reported 24,576. That recovery checked the whole
relocated sentinel before unmount, read-only scanning and eject.

The fresh producer now refreshes the bound mounted root after recording the
returned resize result. Its ticket follows the verified 24,576-block result.
A host test preserves the old cached count until that refresh occurs;
removing the refresh in a private mutation copy fails the test. The new
after-return stop and separate recovery both passed on the device. A fresh
restore from the original backup then passed its complete read-only checks
and eject. The resized work image and its original evidence retained their
hashes throughout restoration.

These cases stop a user process at completed operation boundaries. The
kernel remains running throughout. Their records retain
`kernel_power_loss_tested=false`. Physical Data shrinking and LwVM changes
require their own qualification.
