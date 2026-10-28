// SPDX-License-Identifier: MIT
import Foundation
import ResizeCore

guard CommandLine.arguments.count == 3, let size = Int(CommandLine.arguments[2]) else {
    fputs("Usage: inspect-gpt-header SAVED_HEADER_BLOCK BLOCK_BYTES\n", stderr)
    exit(2)
}
do {
    let block = try SavedFile.readHeaderBlock(at: CommandLine.arguments[1], blockBytes: size)
    let result = try GPTLikeHeaderDiagnostic.inspect(block)
    let report: [String: Any] = [
        "scope": "one saved header block; partition table and entries unchecked",
        "revision": result.revision,
        "revision_kind": result.revisionKind,
        "header_bytes": result.headerBytes,
        "reserved_is_zero": result.reservedIsZero,
        "header_checksum_matches": result.headerChecksumMatches,
        "partition_table_validated": false,
        "resize_supported": false
    ]
    let data = try JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys])
    FileHandle.standardOutput.write(data)
    FileHandle.standardOutput.write(Data("\n".utf8))
} catch {
    fputs("Inspection failed: \(error)\n", stderr)
    exit(1)
}
