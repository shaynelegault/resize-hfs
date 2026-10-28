# SPDX-License-Identifier: MIT
"""Policy tests plus an optional audit of the locally compiled helper."""
import os
from pathlib import Path
import struct
import tempfile
import unittest

import audit


LOADS = '''helper:
Load command 0
      cmd LC_VERSION_MIN_IPHONEOS
  cmdsize 16
  version 9.0
      sdk 27.1
Load command 1
          cmd LC_LOAD_DYLIB
      cmdsize 56
         name /usr/lib/libSystem.B.dylib (offset 24)
Load command 2
          cmd LC_LOAD_DYLIB
      cmdsize 104
         name /System/Library/Frameworks/IOKit.framework/Versions/A/IOKit (offset 24)
'''
IMPORTS = '\n'.join(sorted(audit.EXPECTED_IMPORTS)) + '\n'


def binary(cpu=12, subtype=9, kind=2):
    return struct.pack('<7I', 0xfeedface, cpu, subtype, kind, 3, 176, 0) + bytes(176)


class BinaryAudit(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / 'helper'
        self.path.write_bytes(binary())

    def runner(self, tool, *arguments):
        self.assertEqual(Path(arguments[-1]), self.path)
        if tool == 'nm':
            self.assertEqual(arguments[:-1], ('-u', '-j'))
        return LOADS if tool == 'otool' else IMPORTS

    def test_reviewed_static_platform_and_imports_pass(self):
        result = audit.audit_binary(self.path, self.runner)
        self.assertEqual(result['architecture'], 'armv7')
        self.assertEqual(result['minimum_ios'], '9.0')
        self.assertFalse(result['helper_execution_performed'])
        self.assertEqual(set(result['imports']), audit.EXPECTED_IMPORTS)

    def test_cpu_subtype_and_executable_type_are_required(self):
        for values in [(0x100000c, 9, 2), (12, 11, 2), (12, 9, 1)]:
            self.path.write_bytes(binary(*values))
            with self.subTest(values=values), self.assertRaises(audit.AuditError):
                audit.audit_binary(self.path, self.runner)

    def test_fat_header_and_truncated_load_command_bounds_are_refused(self):
        for data in [b'\xca\xfe\xba\xbe' + bytes(200), binary()[:30]]:
            self.path.write_bytes(data)
            with self.assertRaises(audit.AuditError):
                audit.audit_binary(self.path, self.runner)

    def test_unexpected_active_io_import_fails(self):
        for name in ['_IOServiceOpen', '_IOConnectCallStructMethod', '_fsctl', '_mount', '_open', '_pread', '_dlopen']:
            def runner(tool, *args):
                return LOADS if tool == 'otool' else IMPORTS + name + '\n'
            with self.subTest(import_name=name), self.assertRaisesRegex(audit.AuditError, 'Unexpected imports'):
                audit.audit_binary(self.path, runner)

    def test_empty_or_incomplete_metadata_import_set_fails(self):
        for output in ['', IMPORTS.replace('_sysctlbyname\n', '')]:
            with self.assertRaises(audit.AuditError):
                audit.imports(output)

    def test_only_the_reviewed_lazy_binder_is_optional(self):
        self.assertEqual(set(audit.imports(IMPORTS + 'dyld_stub_binder\n')),
                         audit.EXPECTED_IMPORTS | {'dyld_stub_binder'})
        for suffix in ['dyld_stub_binder\ndyld_stub_binder\n',
                       'dyld_other_helper\n', '_dlopen\n']:
            with self.subTest(suffix=suffix), self.assertRaises(audit.AuditError):
                audit.imports(IMPORTS + suffix)

    def test_macos_newer_ios_or_duplicate_platform_commands_fail(self):
        variants = [LOADS.replace('LC_VERSION_MIN_IPHONEOS', 'LC_VERSION_MIN_MACOSX'),
                    LOADS.replace('version 9.0', 'version 16.0'),
                    LOADS + 'Load command 3\ncmd LC_VERSION_MIN_IPHONEOS\nversion 9.0\n']
        for output in variants:
            with self.subTest(output=output[-80:]), self.assertRaises(audit.AuditError):
                audit.load_commands(output)

    def test_build_version_form_requires_ios_platform_and_exact_minimum(self):
        output = LOADS.replace('cmd LC_VERSION_MIN_IPHONEOS\n  cmdsize 16\n  version 9.0',
                               'cmd LC_BUILD_VERSION\n  cmdsize 24\n  platform IOS\n  minos 9.0')
        self.assertEqual(audit.load_commands(output)['minimum_ios'], '9.0')
        with self.assertRaises(audit.AuditError):
            audit.load_commands(output.replace('platform IOS', 'platform MACOS'))

    def test_changed_library_and_weak_load_modes_are_refused(self):
        variants = [LOADS.replace('/usr/lib/libSystem.B.dylib', '/usr/lib/libOtherX.B.dylib'),
                    LOADS.replace('LC_LOAD_DYLIB', 'LC_LOAD_WEAK_DYLIB', 1)]
        for output in variants:
            with self.assertRaises(audit.AuditError):
                audit.load_commands(output)

    def test_source_replacement_during_tools_fails(self):
        def replaced(tool, *args):
            if tool == 'nm':
                replacement = self.path.with_name('replacement')
                replacement.write_bytes(binary())
                os.replace(replacement, self.path)
            return LOADS if tool == 'otool' else IMPORTS
        with self.assertRaisesRegex(audit.AuditError, 'identity changed'):
            audit.audit_binary(self.path, replaced)

    def test_symlink_directory_and_device_input_fail(self):
        alias = self.path.with_name('alias')
        alias.symlink_to(self.path)
        for path in [alias, self.path.parent, Path('/dev/null')]:
            with self.subTest(path=path.name), self.assertRaises((audit.AuditError, OSError)):
                audit.audit_binary(path, self.runner)

    @unittest.skipUnless(Path('/usr/bin/xcrun').exists(), 'requires installed Xcode tools')
    def test_actual_locally_built_helper(self):
        helper = Path(__file__).resolve().parent / '.build/ios9-image-capabilities'
        if not helper.exists():
            self.skipTest('build-capabilities.sh has not produced the helper')
        result = audit.audit_binary(helper)
        self.assertEqual(result['cpu_type'], 12)
        self.assertEqual(result['cpu_subtype'], 9)
        self.assertEqual(set(result['imports']) - audit.OPTIONAL_LINKER_IMPORTS,
                         audit.EXPECTED_IMPORTS)

    @unittest.skipUnless(Path('/usr/bin/xcrun').exists(), 'requires installed Xcode tools')
    def test_actual_macho_with_an_active_import_name_fails(self):
        helper = Path(__file__).resolve().parent / '.build/ios9-image-capabilities'
        if not helper.exists():
            self.skipTest('build-capabilities.sh has not produced the helper')
        original = helper.read_bytes()
        old, new = b'_IOServiceMatching\0', b'_IOServiceOpen\0'
        self.assertIn(old, original)
        modified = original.replace(old, new + bytes(len(old) - len(new)))
        self.assertEqual(len(modified), len(original))
        self.path.write_bytes(modified)
        with self.assertRaisesRegex(audit.AuditError, 'Unexpected imports: _IOServiceOpen'):
            audit.audit_binary(self.path)


if __name__ == '__main__':
    unittest.main()
