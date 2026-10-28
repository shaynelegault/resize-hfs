// SPDX-License-Identifier: MIT
import Foundation
import ResizeCore

guard CommandLine.arguments.count == 2 else {
    fputs("Usage: resize-inspect SAVED_HFS_VOLUME_PREFIX\n", stderr)
    exit(2)
}
do {
    let header = try SavedFile.readPrimaryHeader(at: CommandLine.arguments[1])
    let report: [String: Any] = [
        "scope": "saved HFS primary header only",
        "format": header.format,
        "version": header.version,
        "attributes": header.attributes,
        "journal_flag": header.hasJournalFlag,
        "content_protection_flag": header.hasContentProtectionFlag,
        "allocation_block_bytes": header.allocationBlockBytes,
        "total_blocks": header.totalBlocks,
        "free_blocks": header.freeBlocks,
        "declared_bytes": header.declaredBytes,
        "reported_free_bytes": header.reportedFreeBytes,
        "resize_supported": false,
        "safe_shrink_size_known": false
    ]
    let data = try JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys])
    FileHandle.standardOutput.write(data)
    FileHandle.standardOutput.write(Data("\n".utf8))
} catch {
    fputs("Inspection failed: \(error)\n", stderr)
    exit(1)
}
