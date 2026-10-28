# SPDX-License-Identifier: MIT
import json
from pathlib import Path
import tempfile
import unittest

from lab.lwvm_recovery.saved_pair_model import (BACKUP, BLOCK, CHUNK, HERE, UNKNOWN, Cut, Window,
                              crc_valid, digest, fixture_header, load_pair,
                              pair_write, reconcile_subset, unmap_subset)


class PairTests(unittest.TestCase):
    def setUp(self):
        (HERE/'cases').mkdir(mode=0o700, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='host-test-', dir=HERE/'cases')
        # Window creates its own exclusive directory and refuses existing inputs.
        path = Path(self.temp.name)
        path.rmdir()
        self.window = Window(path)

    def tearDown(self):
        self.window.close()
        self.temp.cleanup()

    def test_unchanged_pair_uses_primary(self):
        loaded = load_pair(self.window)
        self.assertEqual(loaded.selected, fixture_header(b'A'))
        self.assertFalse(loaded.repair_attempted)

    def test_every_successful_statement_cut(self):
        stages = ['checksum_computed', 'primary_written', 'primary_synchronize_returned',
                  'primary_readback_matched', 'backup_written', 'backup_synchronize_returned',
                  'backup_readback_matched', 'success_gap_cleanup_returned']
        for index, stage in enumerate(stages):
            with self.subTest(stage=stage):
                self.window.write(0, fixture_header(b'A'))
                self.window.write(BACKUP, fixture_header(b'A'))
                with self.assertRaises(Cut):
                    pair_write(self.window, fixture_header(b'B'), cut=stage)
                expected = fixture_header(b'A' if index == 0 else b'B')
                loaded = load_pair(self.window)
                self.assertEqual(loaded.selected, expected)
                self.assertFalse(loaded.repair_attempted)

    def test_valid_primary_wins_over_different_backup(self):
        self.window.write(0, fixture_header(b'B'))
        result = load_pair(self.window)
        self.assertEqual(result.selected, fixture_header(b'B'))
        self.assertFalse(result.repair_attempted)
        self.assertEqual(self.window.read(BACKUP, BLOCK), fixture_header(b'A'))

    def test_torn_primary_uses_and_repairs_old_backup(self):
        with self.assertRaises(Cut):
            pair_write(self.window, fixture_header(b'B'), fault='primary_torn_cut')
        self.assertFalse(crc_valid(self.window.read(0, BLOCK)))
        result = load_pair(self.window)
        self.assertTrue(result.repair_attempted)
        self.assertTrue(result.repair_return)
        self.assertEqual(result.selected, fixture_header(b'A'))
        self.assertEqual(self.window.read(0, BLOCK), self.window.read(BACKUP, BLOCK))

    def test_torn_backup_is_ignored_when_primary_passes(self):
        with self.assertRaises(Cut):
            pair_write(self.window, fixture_header(b'B'), fault='backup_torn_cut')
        result = load_pair(self.window)
        self.assertEqual(result.selected, fixture_header(b'B'))
        self.assertFalse(result.repair_attempted)
        self.assertFalse(crc_valid(self.window.read(BACKUP, BLOCK)))

    def test_failure_requests_whole_metadata_chunk(self):
        for fault in ['primary_write_error', 'primary_readback_error',
                      'backup_write_error', 'backup_readback_error']:
            with self.subTest(fault=fault):
                self.window.write(0, fixture_header(b'A'))
                self.window.write(BACKUP, fixture_header(b'A'))
                self.window.events.clear()
                self.assertFalse(pair_write(self.window, fixture_header(b'B'), fault=fault, effect='poison'))
                request = [e for e in self.window.events if e['event'] == 'provider_unmap']
                self.assertEqual([(e['start'], e['length']) for e in request], [(0, CHUNK)])
                self.assertFalse(crc_valid(self.window.read(0, BLOCK)))
                self.assertFalse(crc_valid(self.window.read(BACKUP, BLOCK)))

    def test_success_requests_only_gap_and_ignores_unmap_status(self):
        self.assertTrue(pair_write(self.window, fixture_header(b'B'), effect='poison', unmap_status=0xe00002c7))
        self.assertEqual(self.window.read(0, BLOCK), fixture_header(b'B'))
        self.assertEqual(self.window.read(BACKUP, BLOCK), fixture_header(b'B'))
        self.assertEqual(self.window.read(BLOCK, 8), bytes([0xdd])*8)

    def test_synchronize_error_is_ignored_before_readback(self):
        self.assertTrue(pair_write(self.window, fixture_header(b'B'), sync_status=0xe00002bc))
        statuses = [e for e in self.window.events if e['event'].endswith('_synchronize_returned')]
        self.assertEqual(len(statuses), 2)
        self.assertTrue(all(e['checked_by_native'] is False for e in statuses))

    def test_fallback_discards_failed_repair_return(self):
        self.window.write(0, bytes(BLOCK))
        result = load_pair(self.window, repair_fault='primary_write_error', effect='poison')
        self.assertEqual(result.status, 'read_status_zero')
        self.assertEqual(result.selected, fixture_header(b'A'))
        self.assertFalse(result.repair_return)
        self.assertFalse(crc_valid(self.window.read(0, BLOCK)))
        self.assertFalse(crc_valid(self.window.read(BACKUP, BLOCK)))
        self.assertIsNone(load_pair(self.window).selected)

    def test_unsupported_unmap_effect_keeps_possible_old_backup(self):
        self.assertFalse(pair_write(self.window, fixture_header(b'B'), fault='backup_write_error',
                                    effect='keep', unmap_status=0xe00002c7))
        self.assertEqual(self.window.read(0, BLOCK), fixture_header(b'B'))
        self.assertEqual(self.window.read(BACKUP, BLOCK), fixture_header(b'A'))

    def test_external_preimage_restores_to_fresh_file(self):
        before, pin = self.window.preimage()
        self.assertFalse(pair_write(self.window, fixture_header(b'B'), fault='backup_readback_error', effect='poison'))
        damaged = digest(self.window.read(0, CHUNK))
        self.assertNotEqual(damaged, pin)
        self.assertEqual(digest(before.read_bytes()), pin)
        recovered = self.window.path.parent/'recovered-window.img'
        with recovered.open('xb') as stream:
            stream.write(before.read_bytes())
        self.assertEqual(digest(recovered.read_bytes()), pin)
        self.assertEqual(digest(self.window.read(0, CHUNK)), damaged)
        self.assertTrue(crc_valid(recovered.read_bytes()[:BLOCK]))

    def test_bounds_and_unknown_flags(self):
        with self.assertRaises(ValueError):
            self.window.write(CHUNK, b'x')
        self.assertTrue(all(value is False for value in UNKNOWN.values()))


class ReconcileTests(unittest.TestCase):
    def fixture(self):
        return [0xf000, 0x0000, 0x0001, 0x1000, 0x1001, 0xf111, 0xf111]+[0xf3ff]*1017

    def test_shrink_frees_trailing_logical_chunks(self):
        result = reconcile_subset(self.fixture(), [2, 2], [2, 1])
        self.assertEqual(result[:7], [0xf000, 0, 1, 0x1000, 0xf111, 0xf111, 0xf111])

    def test_growth_uses_ascending_f111_only(self):
        result = reconcile_subset(self.fixture(), [2, 2], [3, 3])
        self.assertEqual(result[:7], [0xf000, 0, 1, 0x1000, 0x1001, 2, 0x1002])
        self.assertTrue(all(v == 0xf3ff for v in result[7:]))

    def test_new_owner_can_reuse_chunk_released_by_shrink(self):
        result = reconcile_subset(self.fixture(), [2, 2], [3, 1])
        self.assertEqual(result[4], 2)
        self.assertEqual(unmap_subset(self.fixture(), result, [b'a', b'b'], [b'a', b'b']), [4, 5, 6])

    def test_all_new_free_slots_are_unmapped_even_if_previously_free(self):
        old = self.fixture()
        self.assertEqual(unmap_subset(old, old, [b'a', b'b'], [b'a', b'b']), [5, 6])

    def test_changed_uuid_selects_retained_slots_for_unmap(self):
        old = self.fixture()
        self.assertEqual(unmap_subset(old, old, [b'a', b'b'], [b'a', b'c']), [3, 4, 5, 6])

    def test_holes_duplicates_middle_bits_and_exhaustion_refused(self):
        for slot, value in [(2, 0), (2, 3), (2, 0x401), (2, 0x8000)]:
            with self.subTest(value=value):
                candidate = self.fixture();candidate[slot] = value
                with self.assertRaises(ValueError):
                    reconcile_subset(candidate, [2, 2], [2, 2])
        with self.assertRaises(ValueError):
            reconcile_subset(self.fixture(), [2, 2], [10, 10])


if __name__ == '__main__':
    unittest.main(verbosity=2)
