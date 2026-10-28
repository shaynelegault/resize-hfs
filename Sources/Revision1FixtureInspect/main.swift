// SPDX-License-Identifier: MIT
import Foundation
import ResizeCore

guard CommandLine.arguments.count == 7, let blockBytes = Int(CommandLine.arguments[5]),
      let mediaBlocks = UInt64(CommandLine.arguments[6]) else {
    fputs("Usage: inspect-revision1-fixture PRIMARY_HEADER PRIMARY_ENTRIES BACKUP_HEADER BACKUP_ENTRIES BLOCK_BYTES MEDIA_BLOCKS\n", stderr)
    exit(2)
}
do {
    let primary = try SavedFile.snapshotHeaderBlock(at: CommandLine.arguments[1], blockBytes: blockBytes)
    let entries = try SavedFile.snapshotFixture(at: CommandLine.arguments[2])
    let backup = try SavedFile.snapshotHeaderBlock(at: CommandLine.arguments[3], blockBytes: blockBytes)
    let backupEntries = try SavedFile.snapshotFixture(at: CommandLine.arguments[4])
    try SavedFile.requireDistinct([primary, entries, backup, backupEntries])
    let result = try Revision1SnapshotValidator.validate(primaryHeader: primary.bytes, backupHeader: backup.bytes,
                                                            primaryEntries: entries.bytes, backupEntries: backupEntries.bytes,
                                                            blockBytes: blockBytes, mediaBlocks: mediaBlocks)
    let report: [String: Any] = [
        "scope": "caller-supplied revision-1 fixture; no device access",
        "used_count": result.usedCount,
        "first_used_lba": result.firstUsedLBA.map { $0 as Any } ?? NSNull(),
        "last_used_lba": result.lastUsedLBA.map { $0 as Any } ?? NSNull(),
        "used_blocks": result.usedBlocks,
        "used_ranges_contiguous": result.usedRangesAreContiguous,
        "source_snapshot_atomic": false,
        "device_binding_verified": false,
        "lwvm_mapping_verified": false,
        "resize_supported": false
    ]
    let data = try JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys])
    FileHandle.standardOutput.write(data)
    FileHandle.standardOutput.write(Data("\n".utf8))
} catch {
    fputs("Fixture check failed: \(error)\n", stderr)
    exit(1)
}
