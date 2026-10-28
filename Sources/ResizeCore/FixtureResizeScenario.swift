// SPDX-License-Identifier: MIT
/// An in-memory integration of the separate fixture validators. This type
/// does not access a device, select an actual shrink size, or authorize writes.
/// In particular, caller-supplied chunk limits are not derived from the GPT
/// ranges and cannot establish how real LwVM chunks correspond to a volume.
public struct FixtureResizeScenario: Equatable {
    public enum ScenarioError: Error, Equatable {
        case invalidPartitionIndex
        case partitionAbsent
        case unsupportedPartitionType
        case volumeExceedsPartition
        case targetDoesNotShrinkVolume
    }

    public let table: Revision1SnapshotSummary
    public let volume: HFSHeader
    public let geometry: HypotheticalShrink
    public let chunkFixture: HypotheticalLwVMReconciliation

    /// All four table inputs, the HFS header, map and limits are independent
    /// caller-supplied fixture bytes or values. `entryIndex` is zero-based.
    /// The GPT type check uses Apple's HFS type identifier in on-disk byte
    /// order. It does not prove a device-to-partition binding.
    public init(primaryHeader: [UInt8], backupHeader: [UInt8],
                primaryEntries: [UInt8], backupEntries: [UInt8],
                mediaBlockBytes: Int, mediaBlockCount: UInt64,
                entryIndex: Int, hfsHeader: [UInt8], targetBytes: UInt64,
                fixtureMap: [UInt16], fixtureLimits: [Int]) throws {
        let checked = try Revision1SnapshotValidator.validate(
            primaryHeader: primaryHeader, backupHeader: backupHeader,
            primaryEntries: primaryEntries, backupEntries: backupEntries,
            blockBytes: mediaBlockBytes, mediaBlocks: mediaBlockCount)
        func read32(_ bytes: [UInt8], _ i: Int) -> UInt32 {
            UInt32(bytes[i]) | UInt32(bytes[i + 1]) << 8 |
            UInt32(bytes[i + 2]) << 16 | UInt32(bytes[i + 3]) << 24
        }
        func read64(_ bytes: [UInt8], _ i: Int) -> UInt64 {
            UInt64(read32(bytes, i)) | UInt64(read32(bytes, i + 4)) << 32
        }
        let entryCount = Int(read32(primaryHeader, 80))
        let entrySize = Int(read32(primaryHeader, 84))
        guard entryIndex >= 0 && entryIndex < entryCount else {
            throw ScenarioError.invalidPartitionIndex
        }
        let offset = entryIndex * entrySize // bounded by the validated 1 MiB array
        let type = Array(primaryEntries[offset..<(offset + 16)])
        guard type.contains(where: { $0 != 0 }) else { throw ScenarioError.partitionAbsent }
        let hfsType: [UInt8] = [0x00, 0x53, 0x46, 0x48, 0x00, 0x00, 0xaa, 0x11,
                                0xaa, 0x11, 0x00, 0x30, 0x65, 0x43, 0xec, 0xac]
        guard type == hfsType else { throw ScenarioError.unsupportedPartitionType }
        let first = read64(primaryEntries, offset + 32)
        let last = read64(primaryEntries, offset + 40)
        let count = last - first + 1 // ranges were checked by the table validator
        let parsed = try HFSHeaderParser.parse(hfsHeader)
        let (partitionBytes, overflow) = count.multipliedReportingOverflow(by: UInt64(mediaBlockBytes))
        guard !overflow && parsed.declaredBytes <= partitionBytes else {
            throw ScenarioError.volumeExceedsPartition
        }
        guard targetBytes < parsed.declaredBytes else { throw ScenarioError.targetDoesNotShrinkVolume }
        let proposed = try HypotheticalShrink(existingFirst: first, existingBlockCount: count,
                                               mediaBlockCount: mediaBlockCount,
                                               mediaBlockBytes: UInt32(mediaBlockBytes),
                                               filesystemBlockBytes: parsed.allocationBlockBytes,
                                               targetBytes: targetBytes)
        let chunks = try HypotheticalLwVMReconciliation(entries: fixtureMap, limits: fixtureLimits)
        self.table = checked
        self.volume = parsed
        self.geometry = proposed
        self.chunkFixture = chunks
    }
}
