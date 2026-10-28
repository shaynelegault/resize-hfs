# SPDX-License-Identifier: MIT
"""Bounded copies of stable saved regular files into new destinations."""
import hashlib
import json
import os
from pathlib import Path
import stat

MAX_IMAGE_BYTES = 1024 * 1024 * 1024


def identity(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def open_saved(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
            raise ValueError('Expected a saved regular file with one link')
        if not 0 < st.st_size <= MAX_IMAGE_BYTES:
            raise ValueError('Saved image exceeds the one-GiB lab limit or is empty')
        return fd, st
    except BaseException:
        os.close(fd)
        raise


def digest_saved(path):
    fd, before = open_saved(path)
    try:
        digest = hashlib.sha256()
        total = 0
        for block in iter(lambda: os.read(fd, 1024 * 1024), b''):
            total += len(block)
            if total > before.st_size:
                raise ValueError('Saved image changed while reading')
            digest.update(block)
        if total != before.st_size or identity(before) != identity(os.fstat(fd)):
            raise ValueError('Saved image changed while reading')
        return {'bytes': total, 'sha256': digest.hexdigest()}
    finally:
        os.close(fd)


def sync_directory(directory):
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def fresh_copy(source, destination):
    destination = Path(destination).absolute()
    if destination.parent.resolve() != destination.parent:
        raise ValueError('Copy destination has an aliased parent')
    source_fd, before = open_saved(source)
    output_fd = None
    try:
        output_fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        digest = hashlib.sha256()
        total = 0
        for block in iter(lambda: os.read(source_fd, 1024 * 1024), b''):
            total += len(block)
            if total > before.st_size:
                raise ValueError('Copy source grew while reading')
            digest.update(block)
            cursor = 0
            while cursor < len(block):
                written = os.write(output_fd, block[cursor:])
                if written <= 0:
                    raise OSError('Copy write made no progress')
                cursor += written
        if total != before.st_size or identity(before) != identity(os.fstat(source_fd)):
            raise ValueError('Copy source changed while reading')
        os.fsync(output_fd)
        os.close(output_fd)
        output_fd = None
        sync_directory(destination.parent)
        result = digest_saved(destination)
        if result != {'bytes': total, 'sha256': digest.hexdigest()}:
            raise ValueError('Saved copy failed independent hash verification')
        return result
    finally:
        # Partial outputs remain evidence; callers choose a fresh destination.
        if output_fd is not None:
            os.close(output_fd)
        os.close(source_fd)


def new_json(path, value):
    path = Path(path)
    data = (json.dumps(value, indent=2) + '\n').encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as output:
        output.write(data)
        output.flush()
        os.fsync(output.fileno())
    sync_directory(path.parent)


def load_json(path, maximum=1024 * 1024):
    fd, before = open_saved(path)
    try:
        if before.st_size > maximum:
            raise ValueError('Evidence file exceeds its limit')
        data = os.read(fd, before.st_size + 1)
        if len(data) != before.st_size or identity(before) != identity(os.fstat(fd)):
            raise ValueError('Evidence changed while reading')
        return json.loads(data)
    finally:
        os.close(fd)
