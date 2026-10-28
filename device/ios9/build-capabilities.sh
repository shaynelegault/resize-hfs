#!/bin/sh
# SPDX-License-Identifier: MIT
set -eu
task_dir=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
task_build_dir="$task_dir/.build"
mkdir -p "$task_build_dir/tmp" "$task_build_dir/module-cache"
export TMPDIR="$task_build_dir/tmp"
export CLANG_MODULE_CACHE_PATH="$task_build_dir/module-cache"
task_sdk=$(xcrun --sdk iphoneos --show-sdk-path)
xcrun --sdk iphoneos clang -std=c11 -arch armv7 -miphoneos-version-min=9.0 \
    -isysroot "$task_sdk" -marm -Os -fno-builtin -Wall -Wextra -Werror \
    -c "$task_dir/ios9_image_capabilities.c" -o "$task_build_dir/capabilities.o"
xcrun --sdk iphoneos clang -arch armv7 -miphoneos-version-min=9.0 -nostdlib \
    "$task_build_dir/capabilities.o" "$task_dir/libSystem-armv7.tbd" \
    "$task_dir/IOKit-armv7.tbd" -o "$task_build_dir/ios9-image-capabilities"
file "$task_build_dir/ios9-image-capabilities"
xcrun nm -u "$task_build_dir/ios9-image-capabilities" > "$task_build_dir/imports.txt"
xcrun otool -L "$task_build_dir/ios9-image-capabilities" > "$task_build_dir/libraries.txt"
xcrun otool -l "$task_build_dir/ios9-image-capabilities" > "$task_build_dir/load-commands.txt"
python3 "$task_dir/audit.py" "$task_build_dir/ios9-image-capabilities" > "$task_build_dir/binary-audit.json"
echo 'Built unsigned passive inventory; no device operation performed.'
