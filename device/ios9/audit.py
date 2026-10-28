#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit the passive helper's Mach-O platform, libraries and import names.

This audit reads the binary and invokes xcrun inspection tools. It does not
execute the helper or establish its source semantics or runtime compatibility.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
import subprocess
import sys

EXPECTED_LIBRARIES = {
    '/usr/lib/libSystem.B.dylib',
    '/System/Library/Frameworks/IOKit.framework/Versions/A/IOKit',
}
EXPECTED_IMPORTS = {
    '_IOIteratorNext', '_IOObjectGetClass', '_IOObjectRelease',
    '_IOServiceGetMatchingServices', '_IOServiceMatching',
    '___error', '___stack_chk_fail', '___stack_chk_guard',
    '_lstat', '_printf', '_puts', '_strcmp', '_sysctlbyname',
}
# Legacy linkers add this libSystem entry for their lazy symbol stubs.
OPTIONAL_LINKER_IMPORTS = {'dyld_stub_binder'}
MAX_BYTES = 2 * 1024 * 1024


class AuditError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise AuditError(message)


def metadata(st):
    return st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns


def header(data):
    require(len(data) >= 28, 'Mach-O header is truncated')
    magic, cpu, subtype, kind, commands, command_bytes, flags = struct.unpack_from('<7I', data)
    require(magic == 0xfeedface, 'Expected a thin little-endian 32-bit Mach-O')
    require(cpu == 12 and subtype == 9, 'Expected ARMv7 CPU type/subtype')
    require(kind == 2, 'Expected a Mach-O executable')
    require(0 < commands <= 256 and 0 < command_bytes <= len(data) - 28,
            'Mach-O command bounds are invalid')
    return {'cpu_type': cpu, 'cpu_subtype': subtype, 'load_command_count': commands}


def version(value):
    require(re.fullmatch(r'[0-9]+(?:\.[0-9]+){0,2}', value) is not None,
            'Invalid platform version in load commands')
    parts = tuple(int(part) for part in value.split('.'))
    return parts + (0,) * (3 - len(parts))


def load_commands(output):
    platform, libraries, sdk = [], [], None
    blocks = re.split(r'(?m)^Load command [0-9]+\s*\n', output)[1:]
    require(bool(blocks), 'otool reported no load commands')
    for block in blocks:
        found = re.search(r'(?m)^\s*cmd\s+(LC_[A-Z0-9_]+)\s*$', block)
        require(found is not None, 'otool load command is incomplete')
        command = found[1]
        if command.startswith('LC_VERSION_MIN_'):
            require(command == 'LC_VERSION_MIN_IPHONEOS', 'Unexpected minimum-version platform')
            minimum = re.search(r'(?m)^\s*version\s+(\S+)\s*$', block)
            require(minimum is not None, 'Minimum iOS version is missing')
            platform.append(version(minimum[1]))
            found_sdk = re.search(r'(?m)^\s*sdk\s+(\S+)\s*$', block)
            sdk = found_sdk[1] if found_sdk else None
        elif command == 'LC_BUILD_VERSION':
            target = re.search(r'(?m)^\s*platform\s+(\S+)\s*$', block)
            minimum = re.search(r'(?m)^\s*minos\s+(\S+)\s*$', block)
            require(target is not None and target[1] in ('2', 'IOS'), 'Unexpected build-version platform')
            require(minimum is not None, 'Minimum iOS build version is missing')
            platform.append(version(minimum[1]))
            found_sdk = re.search(r'(?m)^\s*sdk\s+(\S+)\s*$', block)
            sdk = found_sdk[1] if found_sdk else None
        if command in ('LC_LOAD_DYLIB', 'LC_LOAD_WEAK_DYLIB', 'LC_REEXPORT_DYLIB', 'LC_LOAD_UPWARD_DYLIB'):
            require(command == 'LC_LOAD_DYLIB', 'Unexpected library load mode')
            name = re.search(r'(?m)^\s*name\s+(.+?)\s+\(offset [0-9]+\)\s*$', block)
            require(name is not None, 'Loaded library name is missing')
            libraries.append(name[1])
    require(platform == [(9, 0, 0)], 'Expected exactly one iOS 9.0 minimum-version command')
    require(len(libraries) == len(EXPECTED_LIBRARIES) and set(libraries) == EXPECTED_LIBRARIES,
            'Linked libraries differ from the reviewed pair')
    return {'minimum_ios': '9.0', 'sdk': sdk, 'linked_libraries': sorted(libraries),
            'load_command_count': len(blocks)}


def imports(output):
    names = output.splitlines()
    malformed = [name for name in names if name not in OPTIONAL_LINKER_IMPORTS and
                 re.fullmatch(r'_[A-Za-z0-9_.$]+', name) is None]
    require(not malformed, 'nm returned an unexpected import format: ' + repr(malformed[:3])[:400])
    require(len(names) == len(set(names)), 'Duplicate undefined import names')
    extra = set(names) - EXPECTED_IMPORTS - OPTIONAL_LINKER_IMPORTS
    require(not extra, 'Unexpected imports: ' + ', '.join(sorted(extra)))
    missing = EXPECTED_IMPORTS - set(names)
    require(not missing, 'Expected metadata imports are missing: ' + ', '.join(sorted(missing)))
    return sorted(names)


def run_tool(tool, *arguments):
    try:
        return subprocess.check_output(['/usr/bin/xcrun', tool, *map(str, arguments)],
                                       text=True, stderr=subprocess.PIPE, timeout=15)
    except (OSError, subprocess.SubprocessError) as error:
        raise AuditError(tool + ' inspection failed') from error


def audit_binary(path, runner=run_tool):
    path = Path(path).absolute()
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and 28 <= before.st_size <= MAX_BYTES,
                'Expected a bounded regular helper binary')
        with os.fdopen(os.dup(fd), 'rb') as binary:
            data = binary.read(MAX_BYTES + 1)
        require(len(data) == before.st_size, 'Helper size changed during read')
        cpu = header(data)
        loaded = load_commands(runner('otool', '-l', path))
        require(cpu['load_command_count'] == loaded.pop('load_command_count'),
                'Mach-O header and otool command counts differ')
        names = imports(runner('nm', '-u', '-j', path))
        require(metadata(before) == metadata(os.fstat(fd)) == metadata(path.lstat()),
                'Helper identity changed during inspection')
        return {'schema': 1, 'kind': 'ios9-passive-helper-binary-audit',
                'binary_file': path.name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                'architecture': 'armv7', **cpu, **loaded, 'imports': names,
                'linker_imports': sorted(set(names) & OPTIONAL_LINKER_IMPORTS),
                'scope': 'Static CPU, minimum iOS, linked library and undefined import checks',
                'helper_execution_performed': False}
    finally:
        os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    args = parser.parse_args(argv)
    try:
        result = audit_binary(args.binary)
    except (AuditError, OSError) as error:
        print('Binary audit failed: ' + str(error), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
