// SPDX-License-Identifier: MIT
import Foundation
import XCTest
@testable import ResizeCore

final class GPTLikeHeaderTests: XCTestCase {
    /// Synthetic header CRCs are independently calculated with Python zlib.
    func fixture(revision: UInt32 = 1, checksum: UInt32 = 0xa52017f2,
                 blockBytes: Int = 4096) -> [UInt8] {
        var block = [UInt8](repeating: 0, count: blockBytes)
        block.replaceSubrange(0..<8, with: "EFI PART".utf8)
        func put32(_ value: UInt32, _ offset: Int) {
            for i in 0..<4 { block[offset + i] = UInt8(truncatingIfNeeded: value >> (8 * i)) }
        }
        put32(revision, 8); put32(92, 12); put32(checksum, 16)
        return block
    }

    func testObservedAndStandardRevisionsAreReportedSeparately() throws {
        let old = try GPTLikeHeaderDiagnostic.inspect(fixture())
        XCTAssertEqual(old.revisionKind, "observed-revision-1")
        XCTAssertTrue(old.reservedIsZero)
        XCTAssertTrue(old.headerChecksumMatches)
        let standard = try GPTLikeHeaderDiagnostic.inspect(fixture(revision: 0x10000, checksum: 0x36425678, blockBytes: 512))
        XCTAssertEqual(standard.revisionKind, "uefi-1.0")
        XCTAssertTrue(standard.headerChecksumMatches)
        let other = try GPTLikeHeaderDiagnostic.inspect(fixture(revision: 0xabcdef12, checksum: 0x6d1b5519))
        XCTAssertEqual(other.revisionKind, "other")
        XCTAssertTrue(other.headerChecksumMatches)
    }

    func testCRCAndInvalidOrTruncatedHeaders() throws {
        XCTAssertEqual(GPTLikeHeaderDiagnostic.crc32(Array("123456789".utf8)), 0xcbf43926)
        var corrupt = fixture()
        corrupt[24] ^= 1
        XCTAssertFalse(try GPTLikeHeaderDiagnostic.inspect(corrupt).headerChecksumMatches)
        corrupt = fixture(); corrupt[20] = 1
        let reserved = try GPTLikeHeaderDiagnostic.inspect(corrupt)
        XCTAssertFalse(reserved.reservedIsZero)
        XCTAssertFalse(reserved.headerChecksumMatches)
        corrupt = fixture(); corrupt[0] = 0
        XCTAssertThrowsError(try GPTLikeHeaderDiagnostic.inspect(corrupt))
        corrupt = fixture(); corrupt[12] = 91
        XCTAssertThrowsError(try GPTLikeHeaderDiagnostic.inspect(corrupt))
        corrupt = fixture(); corrupt[13] = 0xff
        XCTAssertThrowsError(try GPTLikeHeaderDiagnostic.inspect(corrupt))
        XCTAssertThrowsError(try GPTLikeHeaderDiagnostic.inspect(Array(fixture().prefix(511))))
    }

    func testSavedBlockRefusesTruncatedAndInvalidSizes() throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: false)
        defer { try? FileManager.default.removeItem(at: directory) }
        let file = directory.appendingPathComponent("header.bin")
        try Data(fixture()).write(to: file)
        let bytes = try SavedFile.readHeaderBlock(at: file.path, blockBytes: 4096)
        XCTAssertTrue(try GPTLikeHeaderDiagnostic.inspect(bytes).headerChecksumMatches)
        XCTAssertThrowsError(try SavedFile.readHeaderBlock(at: file.path, blockBytes: 513))
        try Data(repeating: 0, count: 4095).write(to: file)
        XCTAssertThrowsError(try SavedFile.readHeaderBlock(at: file.path, blockBytes: 4096))
    }
}
