// SPDX-License-Identifier: MIT
import Foundation

/// A narrow, read-only summary of the primary HFS Plus or HFSX volume header.
/// This does not check the filesystem, allocation bitmap, journal or LwVM map.
public struct HFSHeader: Equatable, Codable {
    public let format: String
    public let version: UInt16
    public let attributes: UInt32
    public let allocationBlockBytes: UInt32
    public let totalBlocks: UInt32
    public let freeBlocks: UInt32

    public var declaredBytes: UInt64 { UInt64(allocationBlockBytes) * UInt64(totalBlocks) }
    public var reportedFreeBytes: UInt64 { UInt64(allocationBlockBytes) * UInt64(freeBlocks) }
    public var hasJournalFlag: Bool { attributes & 0x00002000 != 0 }
    public var hasContentProtectionFlag: Bool { attributes & 0x40000000 != 0 }
}

public enum HeaderError: Error, Equatable {
    case incomplete
    case unsupportedSignature
    case invalidVersion
    case invalidBlockSize
    case invalidBlockCounts
}

public enum HFSHeaderParser {
    public static let volumeHeaderOffset: UInt64 = 1024
    public static let volumeHeaderSize = 512

    /// Accepts only the 512-byte primary header, in on-disk big-endian order.
    public static func parse(_ bytes: [UInt8]) throws -> HFSHeader {
        guard bytes.count == volumeHeaderSize else { throw HeaderError.incomplete }
        func u16(_ i: Int) -> UInt16 { UInt16(bytes[i]) << 8 | UInt16(bytes[i + 1]) }
        func u32(_ i: Int) -> UInt32 {
            UInt32(bytes[i]) << 24 | UInt32(bytes[i + 1]) << 16 |
            UInt32(bytes[i + 2]) << 8 | UInt32(bytes[i + 3])
        }
        let signature = u16(0), version = u16(2)
        let format: String
        switch signature {
        case 0x482b: format = "HFS+"; guard version == 4 else { throw HeaderError.invalidVersion }
        case 0x4858: format = "HFSX"; guard version == 5 else { throw HeaderError.invalidVersion }
        default: throw HeaderError.unsupportedSignature
        }
        let blockSize = u32(40), total = u32(44), free = u32(48)
        guard blockSize >= 512 && blockSize.nonzeroBitCount == 1 else { throw HeaderError.invalidBlockSize }
        guard total > 0 && free <= total && UInt64(blockSize) * UInt64(total) >= 1536 else {
            throw HeaderError.invalidBlockCounts
        }
        return HFSHeader(format: format, version: version, attributes: u32(4),
                         allocationBlockBytes: blockSize, totalBlocks: total, freeBlocks: free)
    }
}
