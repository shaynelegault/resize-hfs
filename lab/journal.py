# SPDX-License-Identifier: MIT
"""Durable checkpoints for the image experiment, with no mutation replay."""
import hashlib
import json
import os
from pathlib import Path
import stat

from .saved_files import identity, sync_directory

ORDER = ('created', 'image-created', 'seeded', 'backup-verified',
         'shrink-requested', 'shrink-returned', 'verified')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def read_journal(path, allow_incomplete_tail=False):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as source:
        st = os.fstat(source.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_size > 1024 * 1024:
            raise ValueError('Invalid operation journal')
        data = source.read(1024 * 1024 + 1)
        if identity(st) != identity(os.fstat(source.fileno())) or len(data) != st.st_size:
            raise ValueError('Operation journal changed while reading')
    if not data.endswith(b'\n'):
        if not allow_incomplete_tail:
            raise ValueError('Operation journal has an incomplete record')
        data = data[:data.rfind(b'\n') + 1]
    if not data:
        raise ValueError('Operation journal has no complete records')
    records, previous = [], '0' * 64
    for line in data.splitlines():
        record = json.loads(line)
        digest = record.pop('sha256')
        if record['previous'] != previous or record['sequence'] != len(records):
            raise ValueError('Operation journal chain differs')
        if hashlib.sha256(canonical(record)).hexdigest() != digest:
            raise ValueError('Operation journal record differs')
        if len(records) >= len(ORDER) or record['state'] not in ORDER or record['state'] != ORDER[len(records)]:
            raise ValueError('Operation checkpoint order differs')
        if records and record['operation'] != records[0]['operation']:
            raise ValueError('Operation identity changed')
        record['sha256'] = digest
        records.append(record)
        previous = digest
    return records


class Journal:
    def __init__(self, path, operation):
        self.path, self.operation = Path(path), operation
        self.fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        self.sequence, self.previous = 0, '0' * 64
        sync_directory(self.path.parent)

    def checkpoint(self, state, **evidence):
        if self.sequence >= len(ORDER) or state != ORDER[self.sequence]:
            raise ValueError('Unexpected operation checkpoint')
        record = {'operation': self.operation, 'sequence': self.sequence,
                  'state': state, 'previous': self.previous, 'evidence': evidence}
        record['sha256'] = hashlib.sha256(canonical(record)).hexdigest()
        line = canonical(record) + b'\n'
        if os.write(self.fd, line) != len(line):
            raise OSError('Incomplete journal write')
        os.fsync(self.fd)
        self.previous = record['sha256']
        self.sequence += 1

    def close(self):
        os.close(self.fd)
