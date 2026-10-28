# Passive iOS 9 capability probe

This ARMv7 helper checks for `iPad2,5` and kernel build `13G36`, then reports
fixed-path file categories and bounded, exact IORegistry class counts. Its
successful output contains generic target information and aggregate values.
The probe's input is the running device; it accepts no storage path or attach
request.

Build on macOS with Xcode's iPhoneOS SDK:

```sh
/bin/sh device/ios9/build-capabilities.sh
python3 -m unittest discover -s device/ios9 -v
```

The build uses explicit interface-only link stubs for the old ARMv7 system
libraries. `audit.py` checks the resulting thin Mach-O CPU/subtype, iOS 9.0
minimum, reviewed library pair and 14 required imports. A changed import
set requires review. Legacy linkers can add the separately allowed
`dyld_stub_binder` runtime symbol for [lazy binding](https://github.com/llvm/llvm-project/blob/main/lld/MachO/SyntheticSections.cpp).
The audit inspects the
file without executing it.

On macOS, test discovery also compiles the actual C counter with mocked
registry functions. Its 19 cases cover partial RPC failure, invalidation,
class-read failures and the 64-entry bound. The host executable is checked for
external registry imports before it runs. Its entry point calls only the
counter; the probe's device entry point remains unexecuted. Run it separately
with `/bin/sh device/ios9/test-passive-count.sh`.

The helper requires signing for the owner's jailbroken device. Sign a separate
copy and use the owner's trusted, device-pinned SSH transport. Keep connection
identifiers and credentials outside this project. The tested signed copy used
an ad hoc signature with SHA-1/SHA-256 digests for the legacy target.

On 28 October 2026 the probe ran on the P105 through its existing pinned iOS
SSH route. The output reported one exact `IOHDIXController`, with the drive
class count initially unavailable. A second run treated a successful match
with a null iterator as the documented empty result and reported zero exact
`IOHDIXHDDriveInKernel` instances. The DiskImages framework, `hdiutil` and tested `hdik`
paths were missing. `mount_hfs` and `fsck_hfs` were symlinks. The temporary
executable and report were removed after the test.

A later signed revision used explicit MIG next/validity results and again
reported one controller and zero drive instances. A valid `kIOReturnNoDevice`
result qualified the end of iteration. Its 14 required imports preserve this
passive scope; the optional lazy binder remains a separate linker allowance.

The candidate header records a 256-byte structure with 64-bit fields at offsets
8 and 16. The probe reports those compiler layout facts. It leaves user-client
access, selector dispatch, backing-file attachment and ownership-bound detach
for separate qualification.

The source imports registry matching/release calls, fixed-path `lstat` and
read-only `sysctlbyname`. Attach, raw-media read and filesystem mutation
interfaces are outside the reviewed import set. Source review and a real
device run support the narrow inventory claim; static import checks alone
cannot establish all runtime behavior.
