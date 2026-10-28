# SPDX-License-Identifier: MIT
"""Original host-only model of bounded rules from the pinned 13G36 trace.

The file contains one synthetic metadata chunk. It is not a mountable LwVM
medium. Poisoning an unmap range is an explicit possible-outcome policy.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import stat
import struct
import zlib

HERE = Path(__file__).resolve().parent
HEADER = BLOCK = 4096
CHUNK = 65536
BACKUP = CHUNK-BLOCK
MAGIC = bytes.fromhex('6a9088cf8afd630ae351e24887e0b98b')
UNKNOWN = {
    'native_durability_qualified': False,
    'native_open_qualified': False,
    'native_header_sanity_qualified': False,
    'provider_unmap_behavior_qualified': False,
    'encryption_updates_qualified': False,
    'native_interruption_recovery_qualified': False,
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def seal(data):
    out = bytearray(data)
    if len(out) != HEADER or out[:16] != MAGIC:
        raise ValueError('model expects one checksum-bearing synthetic header')
    out[44:48] = bytes(4)
    struct.pack_into('<I', out, 44, zlib.crc32(out))
    return bytes(out)


def crc_valid(data):
    return len(data) == HEADER and data[:16] == MAGIC and seal(data) == data


def fixture_header(marker):
    if marker not in (b'A', b'B'):
        raise ValueError('fixture markers are fixed and carry no native meaning')
    data = bytearray(HEADER)
    data[:16] = MAGIC
    data[16:32] = bytes(range(16))
    struct.pack_into('<QI', data, 32, 64*1024*1024, 2)
    data[64] = marker[0]
    return seal(data)


class Cut(Exception):
    pass


class Window:
    """Held descriptor for a fresh, private, ordinary 64 KiB model file."""
    def __init__(self, directory):
        directory = Path(directory).resolve()
        allowed = HERE/'cases'
        if directory.parent != allowed.resolve():
            raise ValueError('cases must be created directly under the private model folder')
        directory.mkdir(mode=0o700)
        self.path = directory/'metadata-window.img'
        self.fd = os.open(self.path, os.O_CREAT|os.O_EXCL|os.O_RDWR|os.O_NOFOLLOW, 0o600)
        assert stat.S_ISREG(os.fstat(self.fd).st_mode)
        os.ftruncate(self.fd, CHUNK)
        self.events = []
        self.write(0, fixture_header(b'A'))
        self.write(BACKUP, fixture_header(b'A'))

    def close(self):
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1

    def read(self, offset, count):
        if offset < 0 or count < 0 or offset+count > CHUNK:
            raise ValueError('read leaves the saved metadata window')
        data = os.pread(self.fd, count, offset)
        if len(data) != count:
            raise OSError('short model read')
        return data

    def write(self, offset, data):
        if offset < 0 or offset+len(data) > CHUNK:
            raise ValueError('write leaves the saved metadata window')
        if os.pwrite(self.fd, data, offset) != len(data):
            raise OSError('short model write')
        os.fsync(self.fd)

    def unmap(self, start, length, effect, returned_status):
        if effect not in ('keep', 'poison'):
            raise ValueError('choose an explicit unmap policy')
        self.events.append({'event': 'provider_unmap', 'start': start, 'length': length,
                            'count': 1, 'options': 0, 'mock_status': returned_status,
                            'effect_policy': effect, 'native_effect_known': False})
        if effect == 'poison':
            self.write(start, bytes([0xdd])*length)

    def preimage(self):
        path = self.path.parent/'external-preimage.bin'
        data = self.read(0, CHUNK)
        fd = os.open(path, os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW, 0o400)
        try:
            if os.write(fd, data) != len(data):
                raise OSError('short preimage write')
            os.fsync(fd)
        finally:
            os.close(fd)
        return path, digest(data)


def pair_write(window, header, *, cut=None, fault=None, effect='keep',
               sync_status=0, unmap_status=0):
    """Checksum, primary, backup, then one first-chunk unmap request.

    Cuts describe host-visible statement boundaries. They do not simulate
    controller ordering, atomic sectors, a power cut, or native kernel execution.
    """
    def event(name, **fields):
        window.events.append({'event': name, **fields})
        if cut == name:
            raise Cut(name)

    candidate = seal(header)
    event('checksum_computed')
    for role, offset in [('primary', 0), ('backup', BACKUP)]:
        if fault == role+'_write_error':
            event(role+'_write_returned_error')
            window.unmap(0, CHUNK, effect, unmap_status)
            event('failure_cleanup_returned')
            return False
        if fault == role+'_torn_cut':
            window.write(offset, candidate[:2048])
            # Ensure this fixture cut changes a CRC-covered byte even though
            # the A/B marker and checksum are in the first half.
            old = window.read(offset+3000, 1)
            window.write(offset+3000, bytes([old[0]^1]))
            event(role+'_synthetic_torn_cut')
            raise Cut(role+'_synthetic_torn_cut')
        window.write(offset, candidate)
        event(role+'_written')
        event(role+'_synchronize_returned', mock_status=sync_status, checked_by_native=False)
        if fault == role+'_readback_error':
            event(role+'_readback_failed')
            window.unmap(0, CHUNK, effect, unmap_status)
            event('failure_cleanup_returned')
            return False
        assert window.read(offset, HEADER) == candidate
        event(role+'_readback_matched')
    window.unmap(BLOCK, CHUNK-2*BLOCK, effect, unmap_status)
    event('success_gap_cleanup_returned')
    return True


@dataclass(frozen=True)
class Load:
    status: str
    selected: bytes | None
    repair_attempted: bool
    repair_return: bool | None


def load_pair(window, *, repair_fault=None, effect='keep'):
    """Only the read/CRC selection layer; native sanity/repair beyond it is unknown."""
    primary = window.read(0, HEADER)
    if crc_valid(primary):
        return Load('read_status_zero', primary, False, None)
    backup = window.read(BACKUP, HEADER)
    if not crc_valid(backup):
        return Load('both_reads_or_crc_failed', None, False, None)
    repaired = pair_write(window, backup, fault=repair_fault, effect=effect)
    # Native 0x80c49a9e overwrites the repair writer result with success.
    return Load('read_status_zero', backup, True, repaired)


def reconcile_subset(old_map, old_counts, new_counts):
    """Fixed partition identities/order with previously complete logical maps.

    This covers the native drop-at-new-ceiling and ascending 0xf111 allocation
    loops. GPT parsing, encryption, relocation and opaque special values remain
    outside this deliberately narrow model.
    """
    if len(old_map) != 1024 or len(old_counts) != len(new_counts) or not 1 <= len(old_counts) <= 8:
        raise ValueError('unsupported fixture shape')
    if any(type(n) is not int or not 1 <= n <= 1024 for n in (*old_counts, *new_counts)):
        raise ValueError('unsupported chunk counts')
    for owner, count in enumerate(old_counts):
        values = [v&1023 for v in old_map if v>>12 == owner]
        if sorted(values) != list(range(count)):
            raise ValueError('fixture map has a hole or duplicate')
    if any(not 0 <= value <= 65535 or
           (value>>12 != 15 and (value>>12 >= len(old_counts) or value&0xc00)) for value in old_map):
        raise ValueError('unsupported fixture owner or middle bits')
    result = list(old_map)
    for slot, value in enumerate(result):
        owner = value>>12
        if owner != 15 and value&1023 >= new_counts[owner]:
            result[slot] = 0xf111
    for owner, count in enumerate(new_counts):
        present = {v&1023 for v in result if v>>12 == owner}
        for logical in range(count):
            if logical in present:
                continue
            try:
                slot = result.index(0xf111)
            except ValueError as exc:
                raise ValueError('fixture lacks allocatable chunks') from exc
            result[slot] = owner<<12 | logical
    return result


def unmap_subset(old_map, new_map, old_ids, new_ids):
    """Physical slots selected by the traced post-pair unmap loop.

    Requests include every new 0xf111 slot and newly assigned slots. Actual
    provider effects and error handling remain unqualified.
    """
    if len(old_map) != len(new_map) or len(old_map) != 1024:
        raise ValueError('expected the complete synthetic map')
    slots = []
    for i, (old, new) in enumerate(zip(old_map, new_map)):
        if new >= 0xf000:
            if new == 0xf111:
                slots.append(i)
            continue
        if old >= 0xf000 or (old^new)&1023 or old_ids[old>>12] != new_ids[new>>12]:
            slots.append(i)
    return slots
