#!/bin/sh
# SPDX-License-Identifier: MIT
set -eu
task_dir=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
task_build_dir="$task_dir/.build"
mkdir -p "$task_build_dir/tmp" "$task_build_dir/module-cache"
export TMPDIR="$task_build_dir/tmp"
export CLANG_MODULE_CACHE_PATH="$task_build_dir/module-cache"
task_sdk=$(xcrun --sdk macosx --show-sdk-path)
xcrun --sdk macosx clang -std=c11 -isysroot "$task_sdk" -O1 \
    -Wall -Wextra -Werror "$task_dir/test_passive_count.c" \
    -o "$task_build_dir/test-passive-count-host"
xcrun nm -u -j "$task_build_dir/test-passive-count-host" > "$task_build_dir/passive-count-host-imports.txt"
python3 - "$task_build_dir/passive-count-host-imports.txt" <<'PY'
from pathlib import Path
import sys
names = Path(sys.argv[1]).read_text().splitlines()
if any(name.startswith(('_IO', '_io_')) for name in names):
    raise SystemExit('Host test contains an external registry import')
PY
"$task_build_dir/test-passive-count-host"
