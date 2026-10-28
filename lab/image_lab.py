#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""A fixed-size macOS HFSX experiment on images created by this invocation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import subprocess
import sys
import uuid

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lab.journal import Journal, read_journal
from lab.saved_files import digest_saved, fresh_copy, load_json, new_json, sync_directory

MEDIA = 192 * 1024 * 1024
TARGET = 96 * 1024 * 1024
LATE_SIZE = 4 * 1024 * 1024
REPO = Path(__file__).resolve().parents[1]
ENV = {**os.environ, 'LC_ALL': 'C'}


def run(argv, timeout=60):
    process = subprocess.run([str(x) for x in argv], capture_output=True, env=ENV, timeout=timeout)
    if process.returncode:
        raise RuntimeError(str(argv[0]) + ' failed: ' + process.stderr.decode(errors='replace')[-1500:])
    return process.stdout


def plist(argv):
    return plistlib.loads(run(argv))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def new_directory(path):
    path = Path(path).absolute()
    require(path.parent.resolve() == path.parent, 'Choose a canonical output parent')
    require(not path.exists() and not path.is_symlink(), 'Choose a new output directory')
    path.mkdir(mode=0o700)
    sync_directory(path.parent)
    return path


def build_helper():
    destination = REPO / '.build' / 'image-fsctl'
    destination.parent.mkdir(exist_ok=True)
    require(destination.parent.resolve() == destination.parent, 'Helper build directory is aliased')
    temporary = destination.parent / ('image-fsctl-' + uuid.uuid4().hex)
    run(['/usr/bin/xcrun', 'clang', '-std=c11', '-Wall', '-Wextra', '-Werror', '-O2',
         '-framework', 'CoreFoundation', REPO / 'lab/image_fsctl.c', '-o', temporary])
    os.replace(temporary, destination)
    return destination


def image_inventory(image):
    records = [record for record in plist(['/usr/bin/hdiutil', 'info', '-plist'])['images']
               if record.get('image-path') == str(image)]
    require(len(records) == 1, 'Image attachment is absent or ambiguous')
    return records[0]


def check_binding(image, mount, read_only, volume_name):
    record = image_inventory(image)
    entities = record.get('system-entities', [])
    require(len(entities) == 1, 'Image must have exactly one whole-volume entity')
    entity = entities[0]
    device = entity.get('dev-entry', '')
    require(re.fullmatch(r'/dev/disk[0-9]+', device) is not None, 'Unexpected image device')
    require(entity.get('mount-point') == str(mount), 'Image mount changed')
    require(record.get('owner-uid') == os.getuid() and record.get('image-encrypted') is False,
            'Image owner or encryption differs')
    require(record.get('writeable') is (not read_only) and record.get('blocksize') == 512 and
            record.get('blockcount') == MEDIA // 512, 'Image access or geometry differs')
    disk = plist(['/usr/sbin/diskutil', 'info', '-plist', device])
    require(disk.get('DeviceNode') == device and disk.get('MountPoint') == str(mount) and
            disk.get('VolumeName') == volume_name, 'Virtual volume identity differs')
    require(disk.get('VirtualOrPhysical') == 'Virtual' and disk.get('BusProtocol') == 'Disk Image' and
            disk.get('WholeDisk') is True and disk.get('Internal') is False and
            disk.get('OSInternalMedia') is False and disk.get('SystemImage') is False,
            'Volume is outside the disposable-image scope')
    require(disk.get('FilesystemType') == 'hfs' and disk.get('IOKitSize') == MEDIA and
            disk.get('WritableVolume') is (not read_only), 'Unexpected image filesystem or access')
    return device


class Attachment:
    def __init__(self, image, mount, read_only, volume_name):
        self.image, self.mount = image, mount
        self.read_only, self.volume_name = read_only, volume_name

    def __enter__(self):
        self.mount.mkdir(mode=0o700)
        argv = ['/usr/bin/hdiutil', 'attach', '-nobrowse', '-owners', 'on',
                '-mountpoint', self.mount, '-plist']
        if self.read_only:
            argv.append('-readonly')
        argv.append(self.image)
        run(argv)
        self.device = check_binding(self.image, self.mount, self.read_only, self.volume_name)
        return self

    def __exit__(self, kind, error, trace):
        # Revalidate before detach. Changed evidence leaves the attachment for inspection.
        device = check_binding(self.image, self.mount, self.read_only, self.volume_name)
        require(device == self.device, 'Image device changed before detach')
        run(['/usr/bin/hdiutil', 'detach', device])
        self.mount.rmdir()


def receipt(root, attachment, token):
    image = attachment.image
    before = image.lstat()
    require(image.is_file() and not image.is_symlink() and before.st_nlink == 1,
            'Expected the new lab image file')
    check_binding(image, attachment.mount, attachment.read_only, attachment.volume_name)
    data = {'kind': 'resize-hfs-disposable-image-v1', 'image': str(image),
            'mount': str(attachment.mount), 'device': attachment.device,
            'token': token, 'volume_name': attachment.volume_name, 'owner_uid': os.getuid(),
            'image_inode': before.st_ino, 'image_device': before.st_dev, 'image_bytes': before.st_size,
            'media_bytes': MEDIA, 'target_bytes': TARGET, 'read_only': attachment.read_only}
    path = root / ('lab-' + uuid.uuid4().hex + '.plist')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(plistlib.dumps(data))
        stream.flush()
        os.fsync(stream.fileno())
    return path, data


def native(helper, action, record):
    evidence = Path(record).parent / ('native-' + action + '-' + uuid.uuid4().hex + '.json')
    argv = [str(helper), action, str(record)]
    try:
        process = subprocess.run(argv, capture_output=True, env=ENV, timeout=180)
    except subprocess.TimeoutExpired as error:
        new_json(evidence, {'action': action, 'returncode': None, 'outcome': 'unknown after timeout',
                 'stdout': (error.stdout or b'').decode(errors='replace'),
                 'stderr': (error.stderr or b'').decode(errors='replace')})
        raise RuntimeError('Native ' + action + ' timed out; inspect the retained image and ' + evidence.name) from error
    new_json(evidence, {'action': action, 'returncode': process.returncode,
             'stdout': process.stdout.decode(errors='replace'),
             'stderr': process.stderr.decode(errors='replace')})
    if process.returncode:
        raise RuntimeError('Native ' + action + ' returned an error; inspect the retained image and ' + evidence.name)
    return json.loads(process.stdout)


def content(path, size, seed):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    block = hashlib.shake_256(seed).digest(1024 * 1024)
    with os.fdopen(fd, 'wb') as output:
        for _ in range(size // len(block)):
            output.write(block)
        output.flush()
        os.fsync(output.fileno())
    return digest_saved(path)


def header_geometry(path):
    # Independent bounded readback of the raw fixture, without a device descriptor.
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        primary = os.pread(fd, 512, 1024)
        require(len(primary) == 512 and primary[:4] == b'HX\0\5', 'Expected an HFSX primary header')
        size = int.from_bytes(primary[40:44], 'big') * int.from_bytes(primary[44:48], 'big')
        require(1536 <= size <= os.fstat(fd).st_size, 'HFS image is incomplete')
        alternate = os.pread(fd, 512, size - 1024)
        require(len(alternate) == 512 and alternate[:4] == primary[:4] and
                alternate[40:48] == primary[40:48], 'Alternate HFS geometry differs')
        return size
    finally:
        os.close(fd)


def guards(helper, root, record, data):
    refused = []
    for field, value in [('device', '/dev/disk0'), ('image_inode', data['image_inode'] + 1),
                         ('target_bytes', TARGET + 4096)]:
        changed = {**data, field: value}
        path = root / ('refused-' + field + '.plist')
        path.write_bytes(plistlib.dumps(changed))
        path.chmod(0o600)
        result = subprocess.run([str(helper), 'shrink', str(path)], capture_output=True, env=ENV, timeout=30)
        require(result.returncode == 2 and b'Image operation refused:' in result.stderr,
                'Native helper accepted mismatched evidence')
        refused.append(field)
    require(native(helper, 'probe', record)['volume_bytes'] == MEDIA,
            'Refusal tests changed the filesystem size')
    return refused


def verify_readonly(helper, root, image, token, volume_name, expected, late_digest):
    before = digest_saved(image)
    require(header_geometry(image) == expected, 'Saved header size differs')
    with Attachment(image, root / 'verify-mount', True, volume_name) as attached:
        record, _ = receipt(root, attached, token)
        evidence = native(helper, 'probe', record)
        require(evidence['volume_bytes'] == expected, 'Read-only volume size differs')
        require(digest_saved(attached.mount / 'late.bin') == late_digest, 'Relocated file contents differ')
        check_binding(image, attached.mount, True, volume_name)
        output = run(['/usr/sbin/diskutil', 'verifyVolume', attached.device], timeout=180).decode(errors='replace')
        require('appears to be OK' in output and 'File system check exit code is 0' in output and
                'skipp' not in output.lower() and 'warning' not in output.lower(),
                'Filesystem check did not complete cleanly')
        (root / ('verify-' + image.stem + '.log')).write_text(output)
    require(digest_saved(image) == before, 'Read-only verification changed the image bytes')
    return evidence


class Stopped(Exception):
    pass


def experiment(output, stop_after=None):
    require(platform.system() == 'Darwin', 'The disposable HFS image lab requires macOS')
    root = new_directory(output)
    token = str(uuid.uuid4())
    volume = 'RHFS-Lab-' + token[:8]
    journal = Journal(root / 'journal.jsonl', token)
    helper = build_helper()
    def checkpoint(state, **evidence):
        journal.checkpoint(state, **evidence)
        print(state, flush=True)
        if state == stop_after:
            raise Stopped(state)
    try:
        checkpoint('created', media_bytes=MEDIA, target_bytes=TARGET)
        image = root / 'fixture.dmg'
        run(['/usr/bin/hdiutil', 'create', '-size', '192m', '-layout', 'NONE',
             '-fs', 'Case-sensitive Journaled HFS+', '-volname', volume, '-type', 'UDIF', image])
        image.chmod(0o600)
        checkpoint('image-created')
        with Attachment(image, root / 'seed-mount', False, volume) as attached:
            (attached.mount / '.metadata_never_index').write_bytes(b'')
            (attached.mount / '.resize-hfs-token').write_text(token)
            content(attached.mount / 'filler.bin', 144 * 1024 * 1024, b'resize-hfs filler')
            late_digest = content(attached.mount / 'late.bin', LATE_SIZE, b'resize-hfs relocation sentinel')
            (attached.mount / 'filler.bin').unlink()
            os.sync()
            record, _ = receipt(root, attached, token)
            before_extents = native(helper, 'probe', record)
            require(before_extents['extents'] and all(x['physical'] >= TARGET for x in before_extents['extents']),
                    'Sentinel allocation did not reach beyond the proposed end')
        checkpoint('seeded', late_file=late_digest, old_extents=before_extents)
        backup = fresh_copy(image, root / 'backup.dmg')
        new_json(root / 'backup.json', {'operation': token, 'volume_name': volume,
                 'backup': backup, 'late_file': late_digest, 'media_bytes': MEDIA,
                 'target_bytes': TARGET, 'helper_source_sha256': hashlib.sha256((REPO / 'lab/image_fsctl.c').read_bytes()).hexdigest()})
        checkpoint('backup-verified', backup=backup)
        with Attachment(image, root / 'shrink-mount', False, volume) as attached:
            record, data = receipt(root, attached, token)
            rejected = guards(helper, root, record, data)
            checkpoint('shrink-requested', refused_evidence=rejected)
            result = native(helper, 'shrink', record)
            require(result == {'fsctl_return': 0, 'errno': 0}, 'HFS shrink returned an error')
            checkpoint('shrink-returned', result=result)
            after = native(helper, 'probe', record)
            require(after['volume_bytes'] == TARGET and after['media_bytes'] == MEDIA,
                    'Filesystem or media size differs from the experiment')
            require(all(x['physical'] + x['bytes'] <= TARGET for x in after['extents']),
                    'File extents remain beyond the reduced volume')
            require(digest_saved(attached.mount / 'late.bin') == late_digest, 'File changed during relocation')
        checked = verify_readonly(helper, root, image, token, volume, TARGET, late_digest)
        checkpoint('verified', new_extents=checked, image=digest_saved(image))
        result = {'schema': 1, 'kind': 'macos-hfsx-image-experiment', 'operation': token,
                  'media_bytes': MEDIA, 'filesystem_before': MEDIA, 'filesystem_after': TARGET,
                  'late_file_unchanged': True, 'extent_relocation_verified': True,
                  'readonly_filesystem_check': 'passed', 'readonly_image_hash_unchanged': True,
                  'native_guard_refusals': rejected, 'on_device_qualified': False}
        new_json(root / 'result.json', result)
        return result
    finally:
        journal.close()


def restore(run_dir, output):
    require(platform.system() == 'Darwin', 'Image restore verification requires macOS')
    source = Path(run_dir).absolute()
    require(source.resolve() == source, 'Operation directory is aliased')
    records = read_journal(source / 'journal.jsonl', allow_incomplete_tail=True)
    verified = next((row for row in records if row['state'] == 'backup-verified'), None)
    require(verified is not None, 'Operation has no durable verified backup checkpoint')
    metadata = load_json(source / 'backup.json')
    require(metadata['operation'] == records[0]['operation'] and metadata['media_bytes'] == MEDIA and
            metadata['target_bytes'] == TARGET and metadata['backup'] == verified['evidence']['backup'],
            'Backup receipt differs from its operation journal')
    backup = source / 'backup.dmg'
    require(digest_saved(backup) == metadata['backup'], 'Backup image differs from its receipt')
    root = new_directory(output)
    image = root / 'restored.dmg'
    require(fresh_copy(backup, image) == metadata['backup'], 'Restored image differs from the backup')
    helper = build_helper()
    verified_image = verify_readonly(helper, root, image, metadata['operation'],
                                    metadata['volume_name'], MEDIA, metadata['late_file'])
    result = {'schema': 1, 'kind': 'macos-hfsx-image-restore', 'source_checkpoint': records[-1]['state'],
              'complete_image_matches_backup': True, 'backup': metadata['backup'],
              'filesystem_bytes': verified_image['volume_bytes'], 'sentinel_unchanged': True,
              'readonly_filesystem_check': 'passed', 'on_device_restore_qualified': False}
    new_json(root / 'result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    execute = commands.add_parser('run', help='create a new disposable image and shrink its HFSX filesystem')
    execute.add_argument('--output', required=True, type=Path)
    execute.add_argument('--stop-after', choices=['backup-verified', 'shrink-requested', 'shrink-returned'])
    recovery = commands.add_parser('restore', help='verify a backup by restoring to a fresh image file')
    recovery.add_argument('--run-dir', required=True, type=Path)
    recovery.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        result = experiment(args.output, args.stop_after) if args.command == 'run' else restore(args.run_dir, args.output)
        print(json.dumps(result, indent=2))
    except Stopped as stopped:
        print('Stopped at durable checkpoint: ' + str(stopped), file=sys.stderr)
        return 42
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print('Image lab stopped: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
