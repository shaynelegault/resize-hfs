# SPDX-License-Identifier: MIT
import copy
import os
from pathlib import Path
import plistlib
import tempfile
import unittest

from lab.nand_geometry import inspect, inspect_saved, row_address


def fixture():
    # Constructed properties exercise the mixed integer/data encoding.
    p = {'ppn-device': True, 'ppn-ftl-ver': 2, '#databus': 2, '#ce': 2,
         'ce-bitmap': 0x101, 'caus-ce': (8).to_bytes(4, 'little'),
         'blocks-cau': (2088).to_bytes(4, 'little'), '#block-pages': 128,
         '#page-bytes': 16384, '#spare-bytes': 64, 'page-bits': 7,
         'block-bits': 12, 'cau-bits': 3, 'logical-page-size': 4096,
         'meta-per-logical-page': 16, '#page-sectors': 32,
         'block-stride': 128, '#ce-blocks': 16704, 'mlc-pages': 128}
    c = {'caus': 8, 'blocks-per-cau': 2088, 'pages-per-block-mlc': 128,
         'page-address-bits': 7, 'block-bits': 12, 'cau-bits': 3, 'page-size': 16448}
    p['controllers'] = [copy.deepcopy(c), copy.deepcopy(c)]
    return {'IORegistry': p}


class NANDGeometryTests(unittest.TestCase):
    def test_geometry_arithmetic_and_reference_mismatch(self):
        result = inspect(fixture())
        self.assertEqual(result['geometry']['reported_data_capacity_bytes'], 70061654016)
        self.assertEqual(result['geometry']['erase_data_bytes'], 2097152)
        self.assertEqual(set(result['reference_mismatches']),
                         {'caus_per_ce', 'blocks_per_cau', 'pages_per_block', 'page_bits'})
        self.assertFalse(result['raw_addressing_qualified'])
        self.assertFalse(result['persistent_writes_qualified'])
        self.assertEqual(result['row_layout'], {
            'block_shift': 7, 'cau_shift': 19, 'last_valid_row': 0x3c13ff,
            'mtd_units': 16, 'bytes_per_cau': 4378853376,
        })

    def test_row_boundaries_and_imported_shift_overlap(self):
        g = inspect(fixture())['geometry']
        self.assertEqual(row_address(g, 0, 0, 127), 0x7f)
        self.assertEqual(row_address(g, 0, 1, 0), 0x80)
        self.assertEqual(row_address(g, 0, 2087, 127), 0x413ff)
        self.assertEqual(row_address(g, 1, 0, 0), 0x80000)
        self.assertLess(row_address(g, 0, 2087, 127), row_address(g, 1, 0, 0))
        self.assertEqual(2048 << 8, 1 << 19)

    def test_row_rejects_out_of_range_indices(self):
        g = inspect(fixture())['geometry']
        for cau, block, page in [(-1, 0, 0), (8, 0, 0), (0, -1, 0),
                                 (0, 2088, 0), (0, 0, -1), (0, 0, 128),
                                 (True, 0, 0)]:
            with self.subTest(cau=cau, block=block, page=page):
                with self.assertRaises(ValueError):
                    row_address(g, cau, block, page)

    def test_serials_and_unrelated_properties_do_not_enter_summary(self):
        value = fixture()
        initial = inspect(value)
        value['IORegistry']['controllers'][0]['controller-unique-id'] = b'private-example'
        value['IORegistry']['controllers'][1]['dies'] = [{'die-unique-id': b'other-private-example'}]
        self.assertEqual(inspect(value), initial)

    def test_rejects_inconsistent_geometry(self):
        for key, value in [('ce-bitmap', 1), ('block-stride', 256), ('#ce-blocks', 1),
                           ('#page-sectors', 31), ('#spare-bytes', 32),
                           ('page-bits', 8), ('blocks-cau', 5000), ('cau-bits', 2)]:
            with self.subTest(key=key):
                p = fixture()
                p['IORegistry'][key] = value
                with self.assertRaises(ValueError):
                    inspect(p)

    def test_rejects_missing_malformed_or_boolean_counts(self):
        for value in [None, True, '128', -1, b'\x80', 0, 2**32]:
            with self.subTest(value=value):
                p = fixture()
                p['IORegistry']['#block-pages'] = value
                with self.assertRaises(ValueError):
                    inspect(p)

    def test_rejects_partial_or_differing_controller_inventory(self):
        p = fixture()
        p['IORegistry']['controllers'].pop()
        with self.assertRaises(ValueError):
            inspect(p)
        p = fixture()
        p['IORegistry']['controllers'][1]['pages-per-block-mlc'] = 256
        with self.assertRaises(ValueError):
            inspect(p)

    def test_saved_file_rejects_symlinks_and_devices(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'nand.plist'
            path.write_bytes(plistlib.dumps(fixture()))
            result = inspect_saved(path)
            self.assertEqual(result['geometry'], inspect(fixture())['geometry'])
            link = Path(directory) / 'link'
            link.symlink_to(path)
            with self.assertRaises(OSError):
                inspect_saved(link)
        with self.assertRaises(ValueError):
            inspect_saved(os.devnull)


if __name__ == '__main__':
    unittest.main()
