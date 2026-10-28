# iOS 9 and P105 qualification

The target is `iPad2,5` / P105AP running iOS 9.3.5 build 13G36. Earlier read-only
research found HFSX System and Data volumes behind LightweightVolumeManager.
The partition-facing view reported `EFI PART` with revision `0x00000001` and
4,096-byte logical blocks. The Swift tools retain that raw revision in their
diagnostics.

The portable commands run on the development host. The image helper is a
macOS program that requires Disk Images and Disk Utility to attest the backing
file. Its input format cannot select an iPad's filesystem.

## Before a device writer

1. Establish a restore route that works when normal iOS startup fails. Preserve
   a full-storage backup for data that must survive; a designated disposable
   device can use an accepted erase-and-restore route. Verify compatible
   firmware and DFU/recovery restore access before internal-volume changes.
   Saved volume prefixes cover only their captured ranges.
2. Build an ARMv7 C or Objective-C helper for the exact iOS build. Confirm its
   ABI and privilege requirements using isolated images on that kernel before
   considering the internal mounted filesystem.
3. Qualify filesystem relocation, journal behavior and each error outcome.
   Establish how a filesystem-size result reaches the iOS partition provider.
4. Independently verify LwVM allocation and reconciliation. The fixture model's
   chunk limits are caller inputs; physical chunks need measured bounds and
   generation checks before a write plan can use them.
5. Record every durable step and test recovery after an interrupted operation.
   An uncertain call outcome requires readback and recovery before another
   mutation is considered.

The earlier 13G36 static study found a handler comparing normalized request
`0x80006802` and reading an eight-byte size. Public interface definitions encode
`0x80086802` before normalization. These observations guide the next ABI test;
they leave the complete userspace dispatch and a read-only minimum-size query
unqualified on this target.

## Linux storage and boot

The P105 Linux milestone currently uses a host-served NFS root. Its native
recovery keeps the flash controller disabled. An internal Linux area needs a
verified allocation boundary and a block backend that can write and recover
through the A5 storage stack. Startup without a host has its own boot-chain
requirements. Each result needs a separate device test.
