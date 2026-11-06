#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run the clean image experiment and its durable stop/restore cases."""
import argparse
import json
from pathlib import Path
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lab.image_lab import MEDIA, TARGET, Stopped, experiment, new_directory, restore
from lab.saved_files import new_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--grow-back', action='store_true',
                        help='include growth to the original size and growth stop/restore cases')
    args = parser.parse_args()
    root = new_directory(args.output)
    cases = []
    checkpoints = [None, 'backup-verified', 'shrink-requested', 'shrink-returned']
    if args.grow_back:
        checkpoints += ['grow-requested', 'grow-returned']
    for checkpoint in checkpoints:
        name = checkpoint or 'clean'
        print('Case: ' + name, flush=True)
        run_dir = root / name
        try:
            result = experiment(run_dir, checkpoint, grow_back=args.grow_back)
            assert checkpoint is None
            assert result['extent_relocation_verified']
            assert result['grow_back_verified'] is args.grow_back
            assert result['filesystem_after'] == (MEDIA if args.grow_back else TARGET)
        except Stopped as stopped:
            assert checkpoint is not None and str(stopped) == checkpoint
        recovered = restore(run_dir, root / (name + '-restored'))
        assert recovered['complete_image_matches_backup']
        cases.append({'checkpoint': name, 'restore_passed': True,
                      'readonly_filesystem_check': 'passed'})
    summary = {'schema': 1, 'scope': 'macOS disposable HFSX images',
               'media_bytes': MEDIA, 'target_bytes': TARGET, 'grow_back': args.grow_back, 'cases': cases,
               'on_device_qualified': False, 'kernel_power_loss_tested': False}
    new_json(root / 'summary.json', summary)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
