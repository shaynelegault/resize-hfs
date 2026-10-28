// SPDX-License-Identifier: MIT
/// Fields and checksum from one saved 4096-byte LwVM header, using the
/// inspected iOS 9.3.5/13G36 contract. Allocation and partition entries remain
/// unchecked, including for a matching checksum.
public struct LwVMHeaderObservation: Equatable {
    public let mediaBytes: UInt64
    public let partitionCount: UInt32
    public let checksumField: UInt32
    public let computedChecksum: UInt32?

    public var checksumKind: String {
        computedChecksum == nil ? "absent-in-this-signature" : "crc32-4096-zeroed-field"
    }

    public var checksumMatches: Bool? {
        computedChecksum.map { $0 == checksumField }
    }
}

public enum LwVMHeaderError: Error, Equatable {
    case invalidHeaderSize
    case unrecognizedSignature
    case unsupportedMediaSize
    case unsupportedPartitionCount
}

public enum LwVMHeaderDiagnostic {
    public static func inspect(_ header: [UInt8]) throws -> LwVMHeaderObservation {
        guard header.count == 4096 else { throw LwVMHeaderError.invalidHeaderSize }
        let signature = Array(header.prefix(16))
        let checksummed: [UInt8] = [0x6a, 0x90, 0x88, 0xcf, 0x8a, 0xfd, 0x63, 0x0a,
                                   0xe3, 0x51, 0xe2, 0x48, 0x87, 0xe0, 0xb9, 0x8b]
        let unchecked: [UInt8] = [0xb1, 0x89, 0xa5, 0x19, 0x4f, 0x59, 0x4b, 0x1d,
                                 0xad, 0x44, 0x1e, 0x12, 0x7a, 0xaf, 0x45, 0x39]
        guard signature == checksummed || signature == unchecked else {
            throw LwVMHeaderError.unrecognizedSignature
        }
        func little32(_ offset: Int) -> UInt32 {
            UInt32(header[offset]) | UInt32(header[offset + 1]) << 8 |
            UInt32(header[offset + 2]) << 16 | UInt32(header[offset + 3]) << 24
        }
        let mediaBytes = UInt64(little32(0x20)) | UInt64(little32(0x24)) << 32
        guard mediaBytes > 0, mediaBytes % 4096 == 0 else {
            throw LwVMHeaderError.unsupportedMediaSize
        }
        let count = little32(0x28)
        guard (1...8).contains(count) else { throw LwVMHeaderError.unsupportedPartitionCount }
        var computed: UInt32?
        if signature == checksummed {
            var bytes = header
            bytes[0x2c...0x2f] = [0, 0, 0, 0]
            computed = GPTLikeHeaderDiagnostic.crc32(bytes)
        }
        return LwVMHeaderObservation(mediaBytes: mediaBytes, partitionCount: count,
                                    checksumField: little32(0x2c), computedChecksum: computed)
    }
}
