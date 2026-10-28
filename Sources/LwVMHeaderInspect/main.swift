// SPDX-License-Identifier: MIT
import Foundation
import ResizeCore

guard CommandLine.arguments.count == 2 else {
    fputs("Usage: inspect-lwvm-header SAVED_HEADER_OR_IMAGE\n", stderr)
    exit(2)
}
do {
    let bytes = try SavedFile.readHeaderBlock(at: CommandLine.arguments[1], blockBytes: 4096)
    let result = try LwVMHeaderDiagnostic.inspect(bytes)
    let report: [String: Any] = [
        "scope": "one saved 4096-byte LwVM header; iOS 9.3.5/13G36 checksum contract",
        "media_bytes": result.mediaBytes,
        "partition_count": result.partitionCount,
        "checksum_kind": result.checksumKind,
        "checksum_field": result.checksumField,
        "computed_checksum": result.computedChecksum.map { $0 as Any } ?? NSNull(),
        "checksum_matches": result.checksumMatches.map { $0 as Any } ?? NSNull(),
        "partition_entries_validated": false,
        "physical_allocation_validated": false,
        "header_pair_validated": false,
        "resize_supported": false
    ]
    let data = try JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys])
    FileHandle.standardOutput.write(data)
    FileHandle.standardOutput.write(Data("\n".utf8))
} catch {
    fputs("Inspection failed: \(error)\n", stderr)
    exit(1)
}
