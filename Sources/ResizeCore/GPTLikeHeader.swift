// SPDX-License-Identifier: MIT
/// Diagnostic of a single saved GPT-like header block. A match does not
/// validate a partition table, its entries or the meaning of revision 1.
public struct GPTLikeHeaderObservation: Equatable {
    public let revision: UInt32
    public let headerBytes: UInt32
    public let reservedIsZero: Bool
    public let headerChecksumMatches: Bool

    public var revisionKind: String {
        switch revision {
        case 0x00010000: return "uefi-1.0"
        case 1: return "observed-revision-1"
        default: return "other"
        }
    }
}

public enum GPTLikeHeaderError: Error, Equatable {
    case invalidBlockSize
    case missingSignature
    case invalidHeaderSize
}

public enum GPTLikeHeaderDiagnostic {
    /// Checks only signature, raw revision, header size, reserved word and CRC.
    public static func inspect(_ block: [UInt8]) throws -> GPTLikeHeaderObservation {
        guard block.count >= 512 && block.count <= 65536 && block.count.nonzeroBitCount == 1 else {
            throw GPTLikeHeaderError.invalidBlockSize
        }
        guard Array(block.prefix(8)) == Array("EFI PART".utf8) else {
            throw GPTLikeHeaderError.missingSignature
        }
        func little32(_ i: Int) -> UInt32 {
            UInt32(block[i]) | UInt32(block[i + 1]) << 8 |
            UInt32(block[i + 2]) << 16 | UInt32(block[i + 3]) << 24
        }
        let size = little32(12)
        guard size >= 92 && size <= UInt32(block.count) else { throw GPTLikeHeaderError.invalidHeaderSize }
        var header = Array(block.prefix(Int(size)))
        let stored = little32(16)
        header[16...19] = [0, 0, 0, 0]
        return GPTLikeHeaderObservation(revision: little32(8), headerBytes: size,
                                        reservedIsZero: little32(20) == 0,
                                        headerChecksumMatches: crc32(header) == stored)
    }

    /// CRC-32/ISO-HDLC, as used by the UEFI header checksum.
    public static func crc32(_ bytes: [UInt8]) -> UInt32 {
        var crc: UInt32 = 0xffffffff
        for byte in bytes {
            crc ^= UInt32(byte)
            for _ in 0..<8 {
                crc = (crc >> 1) ^ ((crc & 1) == 1 ? 0xedb88320 : 0)
            }
        }
        return crc ^ 0xffffffff
    }
}
