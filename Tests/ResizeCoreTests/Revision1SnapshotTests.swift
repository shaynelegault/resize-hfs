// SPDX-License-Identifier: MIT
import Foundation
import XCTest
@testable import ResizeCore

final class Revision1SnapshotTests: XCTestCase {
    func put32(_ value: UInt32, _ offset: Int, _ bytes: inout [UInt8]) {
        for i in 0..<4 { bytes[offset + i] = UInt8(truncatingIfNeeded: value >> (8 * i)) }
    }
    func put64(_ value: UInt64, _ offset: Int, _ bytes: inout [UInt8]) {
        for i in 0..<8 { bytes[offset + i] = UInt8(truncatingIfNeeded: value >> (8 * i)) }
    }
    func header(primary: Bool) -> [UInt8] {
        var bytes = [UInt8](repeating: 0, count: 512)
        bytes.replaceSubrange(0..<8, with: "EFI PART".utf8)
        put32(1, 8, &bytes); put32(92, 12, &bytes)
        put64(primary ? 1 : 999, 24, &bytes); put64(primary ? 999 : 1, 32, &bytes)
        put64(3, 40, &bytes); put64(997, 48, &bytes)
        for i in 0..<16 { bytes[56 + i] = UInt8(i + 1) }
        put64(primary ? 2 : 998, 72, &bytes); put32(4, 80, &bytes); put32(128, 84, &bytes)
        put32(0x742547f8, 88, &bytes)
        // Independently calculated with Python zlib, not the implementation under test.
        put32(primary ? 0xfb1589c0 : 0x0434dd24, 16, &bytes)
        return bytes
    }
    func entries() -> [UInt8] {
        var bytes = [UInt8](repeating: 0, count: 512)
        bytes[0] = 1; put64(6, 32, &bytes); put64(20, 40, &bytes)
        bytes[128] = 2; put64(21, 160, &bytes); put64(90, 168, &bytes)
        return bytes
    }
    func fixHeader(_ bytes: inout [UInt8]) {
        put32(0, 16, &bytes)
        put32(GPTLikeHeaderDiagnostic.crc32(Array(bytes.prefix(92))), 16, &bytes)
    }
    func replaceArrayChecksum(_ array: [UInt8], _ a: inout [UInt8], _ b: inout [UInt8]) {
        let crc = GPTLikeHeaderDiagnostic.crc32(array)
        put32(crc, 88, &a); fixHeader(&a)
        put32(crc, 88, &b); fixHeader(&b)
    }
    func check(_ a: [UInt8], _ b: [UInt8], _ x: [UInt8], _ y: [UInt8],
               blocks: UInt64 = 1000) throws -> Revision1SnapshotSummary {
        try Revision1SnapshotValidator.validate(primaryHeader: a, backupHeader: b,
                                                primaryEntries: x, backupEntries: y,
                                                blockBytes: 512, mediaBlocks: blocks)
    }

    func testMatchingSyntheticMirrorsAndInclusiveTotals() throws {
        let result = try check(header(primary: true), header(primary: false), entries(), entries())
        XCTAssertEqual(result.usedCount, 2)
        XCTAssertEqual(result.firstUsedLBA, 6)
        XCTAssertEqual(result.lastUsedLBA, 90)
        XCTAssertEqual(result.usedBlocks, 85)
        XCTAssertTrue(result.usedRangesAreContiguous)
    }

    func testHeaderCRCRevisionAndPairMismatchFail() {
        let array = entries()
        var a = header(primary: true), b = header(primary: false)
        a[24] ^= 1
        XCTAssertThrowsError(try check(a, b, array, array)) { XCTAssertEqual($0 as? Revision1SnapshotError, .invalidHeader) }
        a = header(primary: true); put32(0x10000, 8, &a); fixHeader(&a)
        XCTAssertThrowsError(try check(a, b, array, array)) { XCTAssertEqual($0 as? Revision1SnapshotError, .invalidHeader) }
        a = header(primary: true); b[56] ^= 1; fixHeader(&b)
        XCTAssertThrowsError(try check(a, b, array, array)) { XCTAssertEqual($0 as? Revision1SnapshotError, .inconsistentHeaders) }
    }

    func testEntryCRCAndCRCCollisionAreBothChecked() {
        let a = header(primary: true), b = header(primary: false), original = entries()
        var altered = original; altered[32] ^= 1
        XCTAssertThrowsError(try check(a, b, original, altered)) { XCTAssertEqual($0 as? Revision1SnapshotError, .invalidEntryArray) }
        // A deliberately distinct array with the same CRC verifies byte-for-byte comparison.
        altered = original; altered[0] = 3; altered.replaceSubrange(508..<512, with: [0x03, 0x8f, 0x69, 0x54])
        XCTAssertEqual(GPTLikeHeaderDiagnostic.crc32(altered), 0x742547f8)
        XCTAssertNotEqual(original, altered)
        XCTAssertThrowsError(try check(a, b, original, altered)) { XCTAssertEqual($0 as? Revision1SnapshotError, .inconsistentEntryArrays) }
        XCTAssertThrowsError(try check(a, b, Array(original.dropLast()), original)) { XCTAssertEqual($0 as? Revision1SnapshotError, .invalidEntryArray) }
    }

    func testOutOfBoundsAndOverlappingRangesFail() {
        var a = header(primary: true), b = header(primary: false), data = entries()
        put64(2, 32, &data); replaceArrayChecksum(data, &a, &b)
        XCTAssertThrowsError(try check(a, b, data, data)) { XCTAssertEqual($0 as? Revision1SnapshotError, .invalidPartitionRange) }
        a = header(primary: true); b = header(primary: false); data = entries()
        put64(20, 160, &data); replaceArrayChecksum(data, &a, &b)
        XCTAssertThrowsError(try check(a, b, data, data)) { XCTAssertEqual($0 as? Revision1SnapshotError, .overlappingPartitions) }
    }

    func testGapAndNoUsedEntriesDoNotReportAContiguousSpan() throws {
        var a = header(primary: true), b = header(primary: false), data = entries()
        put64(22, 160, &data); replaceArrayChecksum(data, &a, &b)
        let gap = try check(a, b, data, data)
        XCTAssertEqual(gap.usedCount, 2)
        XCTAssertEqual(gap.usedBlocks, 84)
        XCTAssertFalse(gap.usedRangesAreContiguous)
        data = [UInt8](repeating: 0, count: 512); replaceArrayChecksum(data, &a, &b)
        let empty = try check(a, b, data, data)
        XCTAssertEqual(empty.usedCount, 0)
        XCTAssertNil(empty.firstUsedLBA)
        XCTAssertNil(empty.lastUsedLBA)
        XCTAssertEqual(empty.usedBlocks, 0)
        XCTAssertFalse(empty.usedRangesAreContiguous)
    }

    func testArrayLimitAndTableOffsetOverflowFail() {
        var a = header(primary: true), b = header(primary: false)
        put32(8193, 80, &a); fixHeader(&a)
        XCTAssertThrowsError(try check(a, b, entries(), entries())) { XCTAssertEqual($0 as? Revision1SnapshotError, .invalidEntryArray) }
        a = header(primary: true); put64(UInt64.max, 72, &a); fixHeader(&a)
        XCTAssertThrowsError(try check(a, b, entries(), entries())) { XCTAssertEqual($0 as? Revision1SnapshotError, .arithmeticOverflow) }
        b = header(primary: false)
        XCTAssertThrowsError(try check(header(primary: true), b, entries(), entries(), blocks: 2)) { XCTAssertEqual($0 as? Revision1SnapshotError, .invalidGeometry) }
    }

    func testCompleteSavedFixtureRejectsSymlinkDirectoryAndOversize() throws {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: false)
        defer { try? FileManager.default.removeItem(at: dir) }
        let file = dir.appendingPathComponent("entries.bin")
        try Data(entries()).write(to: file)
        XCTAssertEqual(try SavedFile.readFixture(at: file.path), entries())
        let original = try SavedFile.snapshotFixture(at: file.path)
        XCTAssertThrowsError(try SavedFile.requireDistinct([original, original]))
        let hardLink = dir.appendingPathComponent("hardlink")
        try FileManager.default.linkItem(at: file, to: hardLink)
        let alias = try SavedFile.snapshotFixture(at: hardLink.path)
        XCTAssertThrowsError(try SavedFile.requireDistinct([original, alias]))
        let other = dir.appendingPathComponent("other.bin")
        try Data(entries()).write(to: other)
        XCTAssertNoThrow(try SavedFile.requireDistinct([original, SavedFile.snapshotFixture(at: other.path)]))
        let link = dir.appendingPathComponent("link")
        try FileManager.default.createSymbolicLink(at: link, withDestinationURL: file)
        XCTAssertThrowsError(try SavedFile.readFixture(at: link.path))
        XCTAssertThrowsError(try SavedFile.readFixture(at: dir.path))
        XCTAssertThrowsError(try SavedFile.readFixture(at: file.path, maximumBytes: 511))
    }
}
