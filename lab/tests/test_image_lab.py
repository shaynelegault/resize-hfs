# SPDX-License-Identifier: MIT
import hashlib
import json
import os
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from lab import image_lab
from lab.journal import Journal, ORDER, read_journal
from lab.saved_files import digest_saved, fresh_copy, new_json


class SavedImages(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / 'source.bin'
        self.data = hashlib.shake_256(b'resize-hfs saved-file fixture').digest(256 * 1024)
        self.source.write_bytes(self.data)

    def test_complete_copy_matches_independent_digest_and_preserves_source(self):
        target = self.root / 'backup.bin'
        result = fresh_copy(self.source, target)
        self.assertEqual(result, {'bytes': len(self.data), 'sha256': hashlib.sha256(self.data).hexdigest()})
        self.assertEqual(target.read_bytes(), self.data)
        self.assertEqual(self.source.read_bytes(), self.data)
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)

    def test_source_symlink_device_fifo_and_hardlink_are_refused(self):
        link = self.root / 'link'
        link.symlink_to(self.source)
        fifo = self.root / 'fifo'
        os.mkfifo(fifo, 0o600)
        for source in [link, Path('/dev/null'), fifo, self.root]:
            with self.subTest(source=source.name), self.assertRaises((ValueError, OSError)):
                fresh_copy(source, self.root / 'new.bin')
        hard = self.root / 'hard'
        os.link(self.source, hard)
        with self.assertRaises(ValueError):
            digest_saved(hard)

    def test_existing_destination_and_links_are_preserved(self):
        target = self.root / 'existing'
        target.write_bytes(b'preserve this saved file')
        linked = self.root / 'destination-link'
        linked.symlink_to(target)
        dangling = self.root / 'dangling'
        dangling.symlink_to('missing')
        for destination in [target, linked, dangling]:
            with self.subTest(destination=destination.name), self.assertRaises(OSError):
                fresh_copy(self.source, destination)
        self.assertEqual(target.read_bytes(), b'preserve this saved file')
        self.assertTrue(dangling.is_symlink())

    def test_aliased_destination_parent_is_refused(self):
        actual = self.root / 'directory'
        actual.mkdir()
        alias = self.root / 'alias'
        alias.symlink_to(actual, target_is_directory=True)
        with self.assertRaises(ValueError):
            fresh_copy(self.source, alias / 'backup.bin')
        self.assertEqual(list(actual.iterdir()), [])

    def test_source_changed_during_copy_never_gets_a_verified_receipt(self):
        original = os.read
        def changed(fd, count):
            block = original(fd, count)
            if block:
                with self.source.open('ab') as output:
                    output.write(b'changed after the read')
            return block
        with patch('lab.saved_files.os.read', side_effect=changed), self.assertRaises(ValueError):
            fresh_copy(self.source, self.root / 'partial.bin')
        self.assertTrue((self.root / 'partial.bin').exists())

    def test_empty_and_oversized_saved_images_are_refused_before_output(self):
        for size in [0, 1024 * 1024 * 1024 + 1]:
            with self.source.open('wb') as output:
                output.truncate(size)
            with self.assertRaises(ValueError):
                fresh_copy(self.source, self.root / 'backup.bin')
            self.assertFalse((self.root / 'backup.bin').exists())

    def test_receipts_are_new_private_files(self):
        path = self.root / 'receipt.json'
        new_json(path, {'test': True})
        with self.assertRaises(OSError):
            new_json(path, {'test': False})
        self.assertEqual(json.loads(path.read_text()), {'test': True})
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)


class Checkpoints(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.path = self.root / 'journal.jsonl'

    def write(self, states):
        journal = Journal(self.path, 'synthetic-operation')
        try:
            for state in states:
                journal.checkpoint(state, test=True)
        finally:
            journal.close()

    def test_durable_records_preserve_order_identity_and_hash_chain(self):
        self.write(ORDER)
        result = read_journal(self.path)
        self.assertEqual([r['state'] for r in result], list(ORDER))
        self.assertEqual({r['operation'] for r in result}, {'synthetic-operation'})

    def test_mutation_checkpoint_cannot_skip_verified_backup(self):
        journal = Journal(self.path, 'synthetic-operation')
        try:
            journal.checkpoint('created')
            before = self.path.read_bytes()
            with self.assertRaises(ValueError):
                journal.checkpoint('shrink-requested')
            self.assertEqual(self.path.read_bytes(), before)
        finally:
            journal.close()

    def test_torn_tail_is_visible_to_reader_and_recovery_uses_only_complete_prefix(self):
        self.write(ORDER[:4])
        with self.path.open('ab') as output:
            output.write(b'{"incomplete":"shrink-requested"')
        with self.assertRaises(ValueError):
            read_journal(self.path)
        result = read_journal(self.path, allow_incomplete_tail=True)
        self.assertEqual(result[-1]['state'], 'backup-verified')

    def test_corrupt_complete_record_is_refused_even_for_recovery(self):
        self.write(ORDER[:4])
        self.path.write_bytes(self.path.read_bytes().replace(b'"test":true', b'"test":false', 1))
        with self.assertRaises(ValueError):
            read_journal(self.path, allow_incomplete_tail=True)

    def test_existing_journal_is_never_replayed_or_truncated(self):
        self.write(ORDER[:3])
        before = self.path.read_bytes()
        with self.assertRaises(OSError):
            Journal(self.path, 'another-operation')
        self.assertEqual(self.path.read_bytes(), before)

    def test_restore_requires_a_durable_verified_backup_before_creating_output(self):
        self.write(ORDER[:3])
        with patch('lab.image_lab.platform.system', return_value='Darwin'), self.assertRaises(ValueError):
            image_lab.restore(self.root, self.root / 'restore')
        self.assertFalse((self.root / 'restore').exists())


class ImageScope(unittest.TestCase):
    def valid(self):
        image, mount = Path('/private/tmp/run/fixture.dmg'), Path('/private/tmp/run/mount')
        inventory = {'owner-uid': os.getuid(), 'image-encrypted': False, 'writeable': True,
                     'blocksize': 512, 'blockcount': image_lab.MEDIA // 512,
                     'system-entities': [{'dev-entry': '/dev/disk42', 'mount-point': str(mount)}]}
        disk = {'DeviceNode': '/dev/disk42', 'MountPoint': str(mount), 'VolumeName': 'RHFS-Lab-test',
                'VirtualOrPhysical': 'Virtual', 'BusProtocol': 'Disk Image', 'WholeDisk': True,
                'Internal': False, 'OSInternalMedia': False, 'SystemImage': False,
                'FilesystemType': 'hfs', 'TotalSize': image_lab.MEDIA, 'IOKitSize': image_lab.MEDIA,
                'WritableVolume': True}
        return image, mount, inventory, disk

    def test_verified_virtual_whole_image_is_accepted(self):
        image, mount, record, disk = self.valid()
        with patch('lab.image_lab.image_inventory', return_value=record), patch('lab.image_lab.plist', return_value=disk):
            self.assertEqual(image_lab.check_binding(image, mount, False, 'RHFS-Lab-test'), '/dev/disk42')

    def test_physical_internal_partitioned_or_wrong_backing_evidence_is_refused(self):
        changes = [('Internal', True), ('OSInternalMedia', True), ('SystemImage', True),
                   ('VirtualOrPhysical', 'Physical'), ('BusProtocol', 'USB'), ('WholeDisk', False),
                   ('DeviceNode', '/dev/disk0'), ('MountPoint', '/'), ('FilesystemType', 'apfs'),
                   ('IOKitSize', image_lab.MEDIA + 512), ('WritableVolume', False)]
        for field, value in changes:
            image, mount, record, disk = self.valid()
            disk[field] = value
            with self.subTest(field=field), patch('lab.image_lab.image_inventory', return_value=record), \
                 patch('lab.image_lab.plist', return_value=disk), self.assertRaises(ValueError):
                image_lab.check_binding(image, mount, False, 'RHFS-Lab-test')

    def test_shrunk_filesystem_can_keep_the_original_backing_medium(self):
        image, mount, record, disk = self.valid()
        disk['VolumeSize'] = image_lab.TARGET
        disk['TotalSize'] = image_lab.TARGET
        with patch('lab.image_lab.image_inventory', return_value=record), patch('lab.image_lab.plist', return_value=disk):
            self.assertEqual(image_lab.check_binding(image, mount, False, 'RHFS-Lab-test'), '/dev/disk42')

    def test_missing_owner_wrong_geometry_and_extra_entities_are_refused(self):
        for field, value in [('owner-uid', os.getuid() + 1), ('blocksize', 0),
                             ('blockcount', 0), ('writeable', False), ('image-encrypted', True),
                             ('system-entities', []), ('system-entities', [{}, {}])]:
            image, mount, record, disk = self.valid()
            record[field] = value
            with self.subTest(field=field), patch('lab.image_lab.image_inventory', return_value=record), \
                 patch('lab.image_lab.plist', return_value=disk), self.assertRaises(ValueError):
                image_lab.check_binding(image, mount, False, 'RHFS-Lab-test')

    def test_access_evidence_must_be_explicit_booleans(self):
        for layer, field in [('inventory', 'writeable'), ('disk', 'WritableVolume')]:
            for value in [None, 0, 1, 'true', 'false']:
                image, mount, record, disk = self.valid()
                target = record if layer == 'inventory' else disk
                if value is None:
                    del target[field]
                else:
                    target[field] = value
                with self.subTest(layer=layer, value=value), \
                     patch('lab.image_lab.image_inventory', return_value=record), \
                     patch('lab.image_lab.plist', return_value=disk), self.assertRaises(ValueError):
                    image_lab.check_binding(image, mount, False, 'RHFS-Lab-test')


class NativeFailureEvidence(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        journal = Journal(self.root / 'journal.jsonl', 'synthetic-operation')
        for state in ORDER[:5]:
            journal.checkpoint(state)
        journal.close()

    def test_resize_errno_and_streams_survive_failure_without_replay(self):
        stdout = b'{"fsctl_return":-1,"errno":28}\n'
        process = subprocess.CompletedProcess(['synthetic-helper'], 1, stdout, b'synthetic backend diagnostic')
        before = (self.root / 'journal.jsonl').read_bytes()
        with patch('lab.image_lab.subprocess.run', return_value=process) as invoked, self.assertRaises(RuntimeError):
            image_lab.native(Path('/synthetic/helper'), 'shrink', self.root / 'lab.plist')
        self.assertEqual(invoked.call_count, 1)
        evidence = json.loads(next(self.root.glob('native-shrink-*.json')).read_text())
        self.assertEqual(evidence['returncode'], 1)
        self.assertEqual(json.loads(evidence['stdout'])['errno'], 28)
        self.assertEqual(evidence['stderr'], 'synthetic backend diagnostic')
        self.assertEqual((self.root / 'journal.jsonl').read_bytes(), before)
        self.assertEqual(read_journal(self.root / 'journal.jsonl')[-1]['state'], 'shrink-requested')

    def test_timeout_retains_partial_output_and_an_unresolved_checkpoint(self):
        timeout = subprocess.TimeoutExpired(['synthetic-helper'], 180, output=b'synthetic partial output')
        with patch('lab.image_lab.subprocess.run', side_effect=timeout) as invoked, self.assertRaises(RuntimeError):
            image_lab.native(Path('/synthetic/helper'), 'shrink', self.root / 'lab.plist')
        self.assertEqual(invoked.call_count, 1)
        evidence = json.loads(next(self.root.glob('native-shrink-*.json')).read_text())
        self.assertIsNone(evidence['returncode'])
        self.assertEqual(evidence['outcome'], 'unknown after timeout')
        self.assertEqual(evidence['stdout'], 'synthetic partial output')
        self.assertEqual(read_journal(self.root / 'journal.jsonl')[-1]['state'], 'shrink-requested')


if __name__ == '__main__':
    unittest.main()
