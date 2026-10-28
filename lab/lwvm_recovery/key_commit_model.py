# SPDX-License-Identifier: MIT
"""Memory-only key-store ordering model for a fixed retained-key proposal.

All bytes below are invented fixtures. The AES boundary is an identity mock;
this module implements no encryption, native key access or physical writer.
An external store error has an explicit possible-effect policy, just as the
header model makes discard effects explicit.
"""
from __future__ import annotations

from dataclasses import dataclass
import struct

from .saved_pair_model import Cut

DISK_ID = bytes(range(16))
PARTITION_ID = bytes(range(16, 32))
SYNTHETIC_KEY = bytes([0x5a]) * 32


def fixture_envelope(prefix):
    if prefix not in (b'A' * 12, b'B' * 12):
        raise ValueError('only the two invented fixture prefixes are supported')
    return prefix + DISK_ID + struct.pack('<I', 1) + PARTITION_ID + SYNTHETIC_KEY


@dataclass(frozen=True)
class Faults:
    capacity_status: int = 0
    capacity_bytes: int = 80
    aes_status: int = 0
    store_status: int = 0
    store_error_effect: str = 'keep'

    def validate(self):
        for status in (self.capacity_status, self.aes_status, self.store_status):
            if type(status) is not int or not 0 <= status <= 0xffffffff:
                raise ValueError('mock statuses must fit an unsigned 32-bit value')
        if type(self.capacity_bytes) is not int or not 0 <= self.capacity_bytes <= 4096:
            raise ValueError('mock capacity must be bounded')
        if self.store_error_effect not in ('keep', 'replace', 'poison'):
            raise ValueError('choose an explicit store-error effect')


class SyntheticStore:
    def __init__(self):
        self.value = fixture_envelope(b'A' * 12)
        self.events = []
        self.attempted = False


@dataclass(frozen=True)
class Result:
    success: bool
    stage: str
    key_store_called: bool
    pair_called: bool
    pair_return: bool | None
    native_key_persistence_qualified: bool = False
    encryption_qualified: bool = False
    power_loss_qualified: bool = False


def commit_unchanged_fixture(store, pair_update, *, faults=Faults(),
                             retained_key_available=True, cut=None):
    """Exercise key-store-before-pair ordering for one unchanged proposal.

    The proposed geometry, UUID and key bytes are fixed. A fresh prefix makes
    the logical envelope differ. pair_update supplies the separate header
    model; a false result leaves the already returned key-store effect intact.
    Cuts stop Python at returned-call boundaries while the kernel is absent.
    """
    if not isinstance(store, SyntheticStore) or not callable(pair_update):
        raise ValueError('expected the synthetic store and an explicit pair callback')
    if type(retained_key_available) is not bool:
        raise ValueError('retained key availability must be explicit')
    if cut not in (None, 'retained_key_loaded', 'capacity_returned', 'aes_returned',
                   'key_store_returned', 'pair_returned'):
        raise ValueError('unknown model boundary')
    faults.validate()
    if store.attempted or store.value != fixture_envelope(b'A' * 12):
        raise ValueError('each invented preimage permits one update attempt')
    store.attempted = True

    def event(name, **fields):
        store.events.append({'event': name, **fields})
        if cut == name:
            raise Cut(name)

    if not retained_key_available:
        event('retained_key_unavailable')
        return Result(False, 'retained_key_unavailable', False, False, None)
    event('retained_key_loaded')
    candidate = fixture_envelope(b'B' * 12)
    event('capacity_returned', mock_status=faults.capacity_status,
          capacity=faults.capacity_bytes, required=len(candidate))
    if faults.capacity_status or faults.capacity_bytes < len(candidate):
        return Result(False, 'key_preparation_failed', False, False, None)
    event('aes_returned', mock_status=faults.aes_status, algorithm_mock='identity')
    if faults.aes_status:
        return Result(False, 'key_preparation_failed', False, False, None)
    if not faults.store_status or faults.store_error_effect == 'replace':
        store.value = candidate
    elif faults.store_error_effect == 'poison':
        store.value = bytes([0xdd]) * len(candidate)
    event('key_store_returned', mock_status=faults.store_status,
          error_effect=faults.store_error_effect, native_effect_known=False)
    if faults.store_status:
        return Result(False, 'key_store_failed', True, False, None)
    returned = pair_update()
    if type(returned) is not bool:
        raise ValueError('pair callback must retain its boolean result')
    event('pair_returned', returned=returned)
    return Result(returned, 'complete' if returned else 'pair_failed', True, True, returned)
