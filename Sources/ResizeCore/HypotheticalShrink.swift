// SPDX-License-Identifier: MIT
/// A synthetic inclusive-range calculation. This is not a shrink plan and
/// does not inspect a device, filesystem, allocation bitmap, or LwVM mapping.
public struct HypotheticalShrink: Equatable {
    public let existing: BlockRange
    public let reduced: BlockRange
    public let releasedTail: BlockRange
    public let targetBytes: UInt64

    public enum GeometryError: Error, Equatable {
        case invalidBlockSize
        case emptyTarget
        case misalignedTarget
        case sizeOverflow
        case noReleasedSpace
    }

    /// All values are caller-provided hypothetical geometry. The target
    /// retains the existing first block and releases the inclusive suffix.
    public init(existingFirst: UInt64, existingBlockCount: UInt64,
                mediaBlockCount: UInt64, mediaBlockBytes: UInt32,
                filesystemBlockBytes: UInt32, targetBytes: UInt64) throws {
        func validSize(_ size: UInt32) -> Bool {
            size >= 512 && size.nonzeroBitCount == 1
        }
        guard validSize(mediaBlockBytes), validSize(filesystemBlockBytes) else {
            throw GeometryError.invalidBlockSize
        }
        let old = try BlockRange(first: existingFirst, count: existingBlockCount,
                                 mediaBlockCount: mediaBlockCount)
        let (oldBytes, overflow) = old.count.multipliedReportingOverflow(by: UInt64(mediaBlockBytes))
        guard !overflow else { throw GeometryError.sizeOverflow }
        guard targetBytes > 0 else { throw GeometryError.emptyTarget }
        guard targetBytes % UInt64(mediaBlockBytes) == 0 &&
              targetBytes % UInt64(filesystemBlockBytes) == 0 else {
            throw GeometryError.misalignedTarget
        }
        guard targetBytes < oldBytes else { throw GeometryError.noReleasedSpace }
        let keptBlocks = targetBytes / UInt64(mediaBlockBytes)
        let kept = try BlockRange(first: old.first, count: keptBlocks,
                                  mediaBlockCount: mediaBlockCount)
        let (tailFirst, tailOverflow) = kept.lastInclusive.addingReportingOverflow(1)
        guard !tailOverflow else { throw GeometryError.sizeOverflow }
        let tail = try BlockRange(first: tailFirst, count: old.count - keptBlocks,
                                  mediaBlockCount: mediaBlockCount)
        self.existing = old
        self.reduced = kept
        self.releasedTail = tail
        self.targetBytes = targetBytes
    }
}
