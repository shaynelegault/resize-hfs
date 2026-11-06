# SPDX-License-Identifier: MIT
"""Inspect saved iOS NAND registry properties without opening a device."""
import argparse
import hashlib
import json
import os
import plistlib

from .saved_files import identity, open_saved


REFERENCE = {
    'buses': 2, 'chip_enables': 2, 'ce_bitmap': 0x101,
    'caus_per_ce': 2, 'blocks_per_cau': 1064, 'pages_per_block': 256,
    'page_data_bytes': 16384, 'page_oob_bytes': 64, 'page_bits': 8,
}


def row_address(geometry, cau, block, page):
    """Encode a PPN row using the saved registry's address widths."""
    for name, value, bound in (
        ('cau', cau, geometry['caus_per_ce']),
        ('block', block, geometry['blocks_per_cau']),
        ('page', page, geometry['pages_per_block']),
    ):
        if type(value) is not int or not 0 <= value < bound:
            raise ValueError('Invalid ' + name + ' index')
    return (cau << (geometry['page_bits'] + geometry['block_bits']) |
            block << geometry['page_bits'] | page)


def number(properties, name):
    value = properties.get(name)
    if isinstance(value, bytes) and len(value) == 4:
        value = int.from_bytes(value, 'little')
    if type(value) is not int or not 0 < value <= 0xffffffff:
        raise ValueError('Missing or unsupported integer: ' + name)
    return value


def inspect(document):
    if not isinstance(document, dict) or not isinstance(document.get('IORegistry'), dict):
        raise ValueError('Expected one saved IORegistry entry')
    p = document['IORegistry']
    if p.get('ppn-device') is not True or number(p, 'ppn-ftl-ver') != 2:
        raise ValueError('Expected a PPN FTL version 2 registry entry')
    names = {
        'buses': '#databus', 'chip_enables': '#ce', 'ce_bitmap': 'ce-bitmap',
        'caus_per_ce': 'caus-ce', 'blocks_per_cau': 'blocks-cau',
        'pages_per_block': '#block-pages', 'page_data_bytes': '#page-bytes',
        'page_oob_bytes': '#spare-bytes', 'page_bits': 'page-bits',
        'block_bits': 'block-bits', 'cau_bits': 'cau-bits',
        'logical_page_bytes': 'logical-page-size',
        'metadata_per_logical_page': 'meta-per-logical-page',
    }
    g = {key: number(p, name) for key, name in names.items()}
    if not (1 <= g['buses'] <= 4 and g['chip_enables'] <= 32 and
            g['page_bits'] + g['block_bits'] + g['cau_bits'] <= 32):
        raise ValueError('Unsupported bus count or address width')
    if (bin(g['ce_bitmap']).count('1') != g['chip_enables'] or
            g['ce_bitmap'] >> (8 * g['buses'])):
        raise ValueError('Chip-enable bitmap and counts disagree')
    if (g['pages_per_block'] != 1 << g['page_bits'] or
            g['blocks_per_cau'] > 1 << g['block_bits'] or
            g['caus_per_ce'] > 1 << g['cau_bits'] or
            number(p, 'block-stride') != g['pages_per_block'] or
            number(p, '#ce-blocks') != g['blocks_per_cau'] * g['caus_per_ce'] or
            number(p, 'mlc-pages') != g['pages_per_block']):
        raise ValueError('Page, block and CAU properties disagree')
    if (number(p, '#page-sectors') * 512 != g['page_data_bytes'] or
            g['page_data_bytes'] % g['logical_page_bytes'] or
            g['page_data_bytes'] // g['logical_page_bytes'] *
            g['metadata_per_logical_page'] != g['page_oob_bytes']):
        raise ValueError('Logical page and spare-byte properties disagree')
    controllers = p.get('controllers')
    if not isinstance(controllers, list) or len(controllers) != g['chip_enables']:
        raise ValueError('Controller inventory and chip-enable count disagree')
    controller_fields = {
        'caus': g['caus_per_ce'], 'blocks-per-cau': g['blocks_per_cau'],
        'pages-per-block-mlc': g['pages_per_block'], 'page-address-bits': g['page_bits'],
        'block-bits': g['block_bits'], 'cau-bits': g['cau_bits'],
        'page-size': g['page_data_bytes'] + g['page_oob_bytes'],
    }
    for c in controllers:
        if not isinstance(c, dict) or any(number(c, k) != v for k, v in controller_fields.items()):
            raise ValueError('Controller properties disagree with NAND geometry')
    g['erase_data_bytes'] = g['pages_per_block'] * g['page_data_bytes']
    g['reported_data_capacity_bytes'] = (
        g['chip_enables'] * g['caus_per_ce'] * g['blocks_per_cau'] * g['erase_data_bytes'])
    mismatch = {k: {'observed': g[k], 'reference': v}
                for k, v in REFERENCE.items() if g[k] != v}
    return {
        'schema': 1, 'scope': 'saved iOS registry geometry', 'geometry': g,
        'geometry_sha256': hashlib.sha256(json.dumps(g, sort_keys=True).encode()).hexdigest(),
        'row_layout': {
            'block_shift': g['page_bits'],
            'cau_shift': g['page_bits'] + g['block_bits'],
            'last_valid_row': row_address(g, g['caus_per_ce'] - 1,
                                          g['blocks_per_cau'] - 1,
                                          g['pages_per_block'] - 1),
            'mtd_units': g['chip_enables'] * g['caus_per_ce'],
            'bytes_per_cau': g['blocks_per_cau'] * g['erase_data_bytes'],
        },
        'imported_reference_matches': not mismatch, 'reference_mismatches': mismatch,
        'raw_addressing_qualified': False, 'ios_logical_mapping_qualified': False,
        'persistent_writes_qualified': False,
    }


def inspect_saved(path):
    fd, before = open_saved(path)
    try:
        if before.st_size > 1024 * 1024:
            raise ValueError('Registry evidence exceeds one MiB')
        data = os.read(fd, before.st_size + 1)
        if len(data) != before.st_size or identity(before) != identity(os.fstat(fd)):
            raise ValueError('Registry evidence changed during the read')
        result = inspect(plistlib.loads(data))
        result['source_sha256'] = hashlib.sha256(data).hexdigest()
        return result
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('saved_nand_plist')
    parser.add_argument('--compare', metavar='SECOND_SAVED_PLIST')
    args = parser.parse_args()
    result = inspect_saved(args.saved_nand_plist)
    if args.compare:
        second = inspect_saved(args.compare)
        result['comparison'] = {
            'source_sha256': second['source_sha256'],
            'geometry_matches': result['geometry'] == second['geometry'],
        }
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
