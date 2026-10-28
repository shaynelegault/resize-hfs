// SPDX-License-Identifier: MIT
/// A bounded consistency check for caller-supplied synthetic or saved files.
/// It does not establish an atomic snapshot, iOS device binding, LwVM chunk
/// ownership, a valid standard GPT, or permission to modify anything.
public struct Revision1SnapshotSummary: Equatable {
    public let usedCount: Int
    public let firstUsedLBA: UInt64?
    public let lastUsedLBA: UInt64?
    public let usedBlocks: UInt64
    public let usedRangesAreContiguous: Bool
}

public enum Revision1SnapshotError: Error, Equatable {
    case invalidGeometry
    case invalidHeader
    case inconsistentHeaders
    case invalidEntryArray
    case inconsistentEntryArrays
    case invalidPartitionRange
    case overlappingPartitions
    case arithmeticOverflow
}

public enum Revision1SnapshotValidator {
    public static let maximumArrayBytes = 1_048_576

    private struct Header {
        let current: UInt64
        let alternate: UInt64
        let firstUsable: UInt64
        let lastUsable: UInt64
        let diskGuid: [UInt8]
        let arrayLBA: UInt64
        let entryCount: UInt32
        let entryBytes: UInt32
        let arrayChecksum: UInt32
    }

    private static func read32(_ bytes: [UInt8], _ offset: Int) -> UInt32 {
        UInt32(bytes[offset]) | UInt32(bytes[offset + 1]) << 8 |
        UInt32(bytes[offset + 2]) << 16 | UInt32(bytes[offset + 3]) << 24
    }

    private static func read64(_ bytes: [UInt8], _ offset: Int) -> UInt64 {
        UInt64(read32(bytes, offset)) | UInt64(read32(bytes, offset + 4)) << 32
    }

    private static func parseHeader(_ bytes: [UInt8], blockBytes: Int,
                                    mediaBlocks: UInt64, primary: Bool) throws -> Header {
        guard bytes.count == blockBytes,
              let observed = try? GPTLikeHeaderDiagnostic.inspect(bytes),
              observed.revision == 1, observed.headerBytes == 92,
              observed.reservedIsZero, observed.headerChecksumMatches else {
            throw Revision1SnapshotError.invalidHeader
        }
        let current = read64(bytes, 24), alternate = read64(bytes, 32)
        let first = read64(bytes, 40), last = read64(bytes, 48)
        let table = read64(bytes, 72), count = read32(bytes, 80), size = read32(bytes, 84)
        guard current == (primary ? 1 : mediaBlocks - 1),
              alternate == (primary ? mediaBlocks - 1 : 1),
              first >= 2, first <= last, last < mediaBlocks - 1,
              count > 0, size >= 128, size <= 4096, size % 8 == 0 else {
            throw Revision1SnapshotError.invalidHeader
        }
        let arrayBytes = UInt64(count) * UInt64(size)
        guard arrayBytes > 0, arrayBytes <= UInt64(maximumArrayBytes) else {
            throw Revision1SnapshotError.invalidEntryArray
        }
        let blocks = (arrayBytes + UInt64(blockBytes) - 1) / UInt64(blockBytes)
        let (end, overflow) = table.addingReportingOverflow(blocks)
        guard !overflow else { throw Revision1SnapshotError.arithmeticOverflow }
        guard table >= 2, table < mediaBlocks, end <= mediaBlocks,
              primary ? end <= first : (table > last && end <= mediaBlocks - 1) else {
            throw Revision1SnapshotError.invalidHeader
        }
        return Header(current: current, alternate: alternate, firstUsable: first,
                      lastUsable: last, diskGuid: Array(bytes[56..<72]), arrayLBA: table,
                      entryCount: count, entryBytes: size, arrayChecksum: read32(bytes, 88))
    }

    public static func validate(primaryHeader: [UInt8], backupHeader: [UInt8],
                                primaryEntries: [UInt8], backupEntries: [UInt8],
                                blockBytes: Int, mediaBlocks: UInt64) throws -> Revision1SnapshotSummary {
        guard blockBytes >= 512, blockBytes <= 65536, blockBytes.nonzeroBitCount == 1,
              mediaBlocks >= 3 else { throw Revision1SnapshotError.invalidGeometry }
        let a = try parseHeader(primaryHeader, blockBytes: blockBytes, mediaBlocks: mediaBlocks, primary: true)
        let b = try parseHeader(backupHeader, blockBytes: blockBytes, mediaBlocks: mediaBlocks, primary: false)
        guard a.firstUsable == b.firstUsable, a.lastUsable == b.lastUsable,
              a.diskGuid == b.diskGuid, a.entryCount == b.entryCount,
              a.entryBytes == b.entryBytes, a.arrayChecksum == b.arrayChecksum else {
            throw Revision1SnapshotError.inconsistentHeaders
        }
        let expected = Int(UInt64(a.entryCount) * UInt64(a.entryBytes))
        guard primaryEntries.count == expected, backupEntries.count == expected,
              GPTLikeHeaderDiagnostic.crc32(primaryEntries) == a.arrayChecksum,
              GPTLikeHeaderDiagnostic.crc32(backupEntries) == b.arrayChecksum else {
            throw Revision1SnapshotError.invalidEntryArray
        }
        guard primaryEntries == backupEntries else { throw Revision1SnapshotError.inconsistentEntryArrays }
        var ranges: [(first: UInt64, last: UInt64)] = []
        for index in 0..<Int(a.entryCount) {
            let offset = index * Int(a.entryBytes)
            if primaryEntries[offset..<(offset + 16)].allSatisfy({ $0 == 0 }) { continue }
            let first = read64(primaryEntries, offset + 32), last = read64(primaryEntries, offset + 40)
            guard first <= last, first >= a.firstUsable, last <= a.lastUsable else {
                throw Revision1SnapshotError.invalidPartitionRange
            }
            ranges.append((first, last))
        }
        ranges.sort { $0.first == $1.first ? $0.last < $1.last : $0.first < $1.first }
        var total: UInt64 = 0
        for (index, range) in ranges.enumerated() {
            if index > 0 && range.first <= ranges[index - 1].last {
                throw Revision1SnapshotError.overlappingPartitions
            }
            let length = range.last - range.first + 1
            let (next, overflow) = total.addingReportingOverflow(length)
            guard !overflow else { throw Revision1SnapshotError.arithmeticOverflow }
            total = next
        }
        let contiguous: Bool
        if let first = ranges.first, let last = ranges.last {
            contiguous = last.last - first.first + 1 == total
        } else { contiguous = false }
        return Revision1SnapshotSummary(usedCount: ranges.count, firstUsedLBA: ranges.first?.first,
                                        lastUsedLBA: ranges.last?.last, usedBlocks: total,
                                        usedRangesAreContiguous: contiguous)
    }
}
