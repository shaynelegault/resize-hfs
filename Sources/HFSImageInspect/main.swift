// SPDX-License-Identifier: MIT
import Foundation
import ResizeCore

guard CommandLine.arguments.count == 2 else {
    fputs("Usage: inspect-hfs-image SAVED_RAW_HFS_IMAGE\n", stderr)
    exit(2)
}
do {
    let summary = try HFSImageHeaders.inspect(at: CommandLine.arguments[1])
    let report: [String: Any] = [
        "scope": "saved primary and filesystem-end alternate HFS header geometry",
        "format": summary.primary.format,
        "version": summary.primary.version,
        "file_bytes": summary.fileBytes,
        "volume_bytes": summary.primary.declaredBytes,
        "allocation_block_bytes": summary.primary.allocationBlockBytes,
        "alternate_header_offset": summary.alternateHeaderOffset,
        "trailing_bytes": summary.trailingBytes,
        "header_geometry_matches": true,
        "filesystem_check_performed": false,
        "resize_supported": false,
        "safe_shrink_size_known": false
    ]
    let encoded = try JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys])
    FileHandle.standardOutput.write(encoded)
    FileHandle.standardOutput.write(Data("\n".utf8))
} catch {
    fputs("Image header inspection failed: \(error)\n", stderr)
    exit(1)
}
