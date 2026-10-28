// SPDX-License-Identifier: MIT
import XCTest
@testable import ResizeCore

final class LwVMHeaderTests: XCTestCase {
    // The checksum is calculated independently with Python zlib over all 4096
    // bytes, with the stored word cleared. The last byte exercises that bound.
    func fixture() -> [UInt8] {
        var bytes = [UInt8](repeating: 0, count: 4096)
        bytes.replaceSubrange(0..<16, with: [0x6a, 0x90, 0x88, 0xcf, 0x8a, 0xfd, 0x63, 0x0a,
                                           0xe3, 0x51, 0xe2, 0x48, 0x87, 0xe0, 0xb9, 0x8b])
        put(64_000_000_000, at: 0x20, count: 8, in: &bytes)
        put(2, at: 0x28, in: &bytes)
        bytes[4095] = 0x5a
        put(0x89c4b6d8, at: 0x2c, in: &bytes)
        return bytes
    }

    func put(_ value: UInt64, at offset: Int, count: Int = 4, in bytes: inout [UInt8]) {
        for i in 0..<count { bytes[offset + i] = UInt8(truncatingIfNeeded: value >> (8 * i)) }
    }

    func testIndependentCRCAndFields() throws {
        let bytes = fixture()
        let observation = try LwVMHeaderDiagnostic.inspect(bytes)
        XCTAssertEqual(observation.mediaBytes, 64_000_000_000)
        XCTAssertEqual(observation.partitionCount, 2)
        XCTAssertEqual(observation.checksumKind, "crc32-4096-zeroed-field")
        XCTAssertEqual(observation.checksumMatches, true)
        XCTAssertEqual(bytes, fixture())
    }

    func testChecksumIncludesFinalByteAndIgnoresStoredWord() throws {
        var bytes = fixture()
        bytes[4095] ^= 1
        XCTAssertEqual(try LwVMHeaderDiagnostic.inspect(bytes).checksumMatches, false)
        bytes = fixture()
        bytes[0x2c] ^= 1
        let observation = try LwVMHeaderDiagnostic.inspect(bytes)
        XCTAssertEqual(observation.checksumMatches, false)
        XCTAssertEqual(observation.computedChecksum, 0x89c4b6d8)
    }

    func testAlternateSignatureHasNoChecksumClaim() throws {
        var bytes = fixture()
        bytes.replaceSubrange(0..<16, with: [0xb1, 0x89, 0xa5, 0x19, 0x4f, 0x59, 0x4b, 0x1d,
                                           0xad, 0x44, 0x1e, 0x12, 0x7a, 0xaf, 0x45, 0x39])
        let observation = try LwVMHeaderDiagnostic.inspect(bytes)
        XCTAssertEqual(observation.checksumKind, "absent-in-this-signature")
        XCTAssertNil(observation.computedChecksum)
        XCTAssertNil(observation.checksumMatches)
    }

    func testRequiresCompleteExactHeaderAndKnownSignature() {
        for count in [0, 512, 4095, 4097] {
            XCTAssertThrowsError(try LwVMHeaderDiagnostic.inspect([UInt8](repeating: 0, count: count))) {
                XCTAssertEqual($0 as? LwVMHeaderError, .invalidHeaderSize)
            }
        }
        var bytes = fixture()
        bytes[0] ^= 1
        XCTAssertThrowsError(try LwVMHeaderDiagnostic.inspect(bytes)) {
            XCTAssertEqual($0 as? LwVMHeaderError, .unrecognizedSignature)
        }
    }

    func testRejectsZeroOrUnalignedMediaAndExcessPartitions() {
        for media in [UInt64(0), 64_000_000_001] {
            var bytes = fixture()
            put(media, at: 0x20, count: 8, in: &bytes)
            XCTAssertThrowsError(try LwVMHeaderDiagnostic.inspect(bytes)) {
                XCTAssertEqual($0 as? LwVMHeaderError, .unsupportedMediaSize)
            }
        }
        for count in [UInt64(0), 9, 12, UInt64(UInt32.max)] {
            var bytes = fixture()
            put(count, at: 0x28, in: &bytes)
            XCTAssertThrowsError(try LwVMHeaderDiagnostic.inspect(bytes)) {
                XCTAssertEqual($0 as? LwVMHeaderError, .unsupportedPartitionCount)
            }
        }
    }
}
