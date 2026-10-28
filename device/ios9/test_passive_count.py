# SPDX-License-Identifier: MIT
"""Compile the actual passive counter with mocked registry calls on macOS."""
from pathlib import Path
import subprocess
import sys
import unittest


class PassiveCounter(unittest.TestCase):
    @unittest.skipUnless(sys.platform == 'darwin' and Path('/usr/bin/xcrun').exists(),
                         'requires macOS Xcode headers and compiler')
    def test_actual_counter_failure_paths(self):
        runner = Path(__file__).resolve().parent / 'test-passive-count.sh'
        result = subprocess.run(['/bin/sh', str(runner)], check=True, capture_output=True,
                                text=True, timeout=60)
        self.assertIn('passive_counter_cases=19 ', result.stdout)
        self.assertIn('external_registry_calls=0', result.stdout)


if __name__ == '__main__':
    unittest.main()
