# SPDX-License-Identifier: MIT
from pathlib import Path
import tempfile
import unittest

from lab.lwvm_recovery.key_commit_model import (
    Faults, Result, SyntheticStore, commit_unchanged_fixture, fixture_envelope,
)
from lab.lwvm_recovery.saved_pair_model import (
    BACKUP, BLOCK, CHUNK, HERE, Cut, Window, crc_valid, digest, fixture_header,
    pair_write,
)


class KeyCommitTests(unittest.TestCase):
    def setUp(self):
        (HERE / 'cases').mkdir(mode=0o700, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='key-test-', dir=HERE / 'cases')
        path = Path(self.temp.name)
        path.rmdir()
        self.window = Window(path)
        self.store = SyntheticStore()
        self.original = self.window.read(0, CHUNK)

    def tearDown(self):
        self.window.close()
        self.temp.cleanup()

    def pair(self, fault=None, effect='keep'):
        def update():
            return pair_write(self.window, fixture_header(b'A'), fault=fault, effect=effect)
        return update

    def test_unchanged_headers_can_accompany_a_changed_key_envelope(self):
        def observed_pair():
            self.assertEqual(self.store.value, fixture_envelope(b'B' * 12))
            self.assertEqual(self.store.events[-1]['event'], 'key_store_returned')
            return self.pair()()
        result = commit_unchanged_fixture(self.store, observed_pair)
        self.assertTrue(result.success)
        self.assertEqual(self.window.read(0, CHUNK), self.original)
        self.assertEqual(self.store.value, fixture_envelope(b'B' * 12))
        self.assertEqual(self.store.value[12:], fixture_envelope(b'A' * 12)[12:])
        self.assertEqual([e['event'] for e in self.store.events][-2:],
                         ['key_store_returned', 'pair_returned'])

    def test_missing_retained_key_changes_neither_store(self):
        result = commit_unchanged_fixture(self.store, self.pair(), retained_key_available=False)
        self.assertFalse(result.key_store_called)
        self.assertFalse(result.pair_called)
        self.assertEqual(self.store.value, fixture_envelope(b'A' * 12))
        self.assertEqual(self.window.read(0, CHUNK), self.original)
        self.assertEqual(self.window.events, [])
        with self.assertRaises(ValueError):
            commit_unchanged_fixture(self.store, self.pair())
        self.assertEqual(self.window.events, [])

    def test_capacity_and_aes_failures_stop_before_both_writes(self):
        cases = [Faults(capacity_status=0xe00002bc), Faults(capacity_bytes=79),
                 Faults(aes_status=0xe00002c7)]
        for faults in cases:
            with self.subTest(faults=faults):
                store = SyntheticStore()
                result = commit_unchanged_fixture(store, self.pair(), faults=faults)
                self.assertEqual(result.stage, 'key_preparation_failed')
                self.assertFalse(result.key_store_called or result.pair_called)
                self.assertEqual(store.value, fixture_envelope(b'A' * 12))
                self.assertEqual(self.window.read(0, CHUNK), self.original)
                self.assertEqual(self.window.events, [])

    def test_store_error_preserves_explicit_possible_effect_and_stops_pair(self):
        expected = {'keep': fixture_envelope(b'A' * 12),
                    'replace': fixture_envelope(b'B' * 12), 'poison': bytes([0xdd]) * 80}
        for effect, value in expected.items():
            with self.subTest(effect=effect):
                store = SyntheticStore()
                result = commit_unchanged_fixture(store, self.pair(),
                    faults=Faults(store_status=0xe00002bc, store_error_effect=effect))
                self.assertEqual(result.stage, 'key_store_failed')
                self.assertTrue(result.key_store_called)
                self.assertFalse(result.pair_called)
                self.assertEqual(store.value, value)
                self.assertEqual(self.window.read(0, CHUNK), self.original)
                self.assertEqual(self.window.events, [])

    def test_pair_failure_keeps_the_preceding_key_store_change(self):
        result = commit_unchanged_fixture(self.store,
                    self.pair('backup_write_error', 'poison'))
        self.assertFalse(result.success)
        self.assertTrue(result.key_store_called and result.pair_called)
        self.assertFalse(result.pair_return)
        self.assertEqual(self.store.value, fixture_envelope(b'B' * 12))
        self.assertFalse(crc_valid(self.window.read(0, BLOCK)))
        self.assertFalse(crc_valid(self.window.read(BACKUP, BLOCK)))

    def test_header_preimage_restore_leaves_key_store_and_failed_work_intact(self):
        preimage, pin = self.window.preimage()
        commit_unchanged_fixture(self.store, self.pair('primary_readback_error', 'poison'))
        damaged_hash = digest(self.window.read(0, CHUNK))
        restored = self.window.path.parent / 'restored-window.img'
        with restored.open('xb') as out:
            out.write(preimage.read_bytes())
        self.assertEqual(digest(restored.read_bytes()), pin)
        self.assertEqual(digest(self.window.read(0, CHUNK)), damaged_hash)
        self.assertEqual(self.store.value, fixture_envelope(b'B' * 12))

    def test_cut_after_store_leaves_old_headers_and_new_envelope(self):
        with self.assertRaises(Cut):
            commit_unchanged_fixture(self.store, self.pair(), cut='key_store_returned')
        self.assertEqual(self.window.read(0, CHUNK), self.original)
        self.assertEqual(self.store.value, fixture_envelope(b'B' * 12))
        self.assertNotIn('pair_returned', [e['event'] for e in self.store.events])
        self.assertEqual(self.window.events, [])

    def test_early_cuts_leave_original_metadata(self):
        for stage in ['retained_key_loaded', 'capacity_returned', 'aes_returned']:
            with self.subTest(stage=stage):
                store = SyntheticStore()
                with self.assertRaises(Cut):
                    commit_unchanged_fixture(store, self.pair(), cut=stage)
                self.assertEqual(store.value, fixture_envelope(b'A' * 12))
                self.assertEqual(self.window.read(0, CHUNK), self.original)
                self.assertEqual(self.window.events, [])

    def test_invalid_configuration_is_refused_before_events(self):
        for faults in [Faults(capacity_status=-1), Faults(capacity_bytes=4097),
                       Faults(aes_status=True), Faults(store_error_effect='assume-atomic')]:
            with self.subTest(faults=faults):
                with self.assertRaises(ValueError):
                    commit_unchanged_fixture(self.store, self.pair(), faults=faults)
                self.assertEqual(self.store.events, [])
        with self.assertRaises(ValueError):
            commit_unchanged_fixture(self.store, self.pair(), cut='power-off')
        self.assertEqual(self.store.events, [])

    def test_fixture_and_result_keep_the_native_boundary_explicit(self):
        with self.assertRaises(ValueError):
            fixture_envelope(b'C' * 12)
        result = commit_unchanged_fixture(self.store, self.pair())
        self.assertIsInstance(result, Result)
        self.assertFalse(result.native_key_persistence_qualified)
        self.assertFalse(result.encryption_qualified)
        self.assertFalse(result.power_loss_qualified)

    def test_callback_exception_retains_changed_store_and_prevents_replay(self):
        def uncertain():
            raise OSError('injected lost pair result')
        with self.assertRaises(OSError):
            commit_unchanged_fixture(self.store, uncertain)
        self.assertEqual(self.store.value, fixture_envelope(b'B' * 12))
        self.assertEqual(self.window.read(0, CHUNK), self.original)
        prior_events = list(self.store.events)
        with self.assertRaises(ValueError):
            commit_unchanged_fixture(self.store, self.pair())
        self.assertEqual(self.store.events, prior_events)

    def test_nonboolean_pair_result_stays_unqualified_and_cannot_repeat(self):
        with self.assertRaises(ValueError):
            commit_unchanged_fixture(self.store, lambda: 0)
        self.assertEqual(self.store.value, fixture_envelope(b'B' * 12))
        self.assertNotIn('pair_returned', [e['event'] for e in self.store.events])
        with self.assertRaises(ValueError):
            commit_unchanged_fixture(self.store, self.pair())


if __name__ == '__main__':
    unittest.main(verbosity=2)
