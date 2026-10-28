// SPDX-License-Identifier: MIT
import Foundation
import XCTest
@testable import ResizeCore
#if canImport(Darwin)
import Darwin
#else
import Glibc
#endif

final class HFSHeaderTests: XCTestCase {
    func syntheticHeader(signature: UInt16 = 0x482b, version: UInt16 = 4,
                         blockSize: UInt32 = 4096, total: UInt32 = 100,
                         free: UInt32 = 25) -> [UInt8] {
        var bytes = [UInt8](repeating: 0, count: 512)
        func put16(_ value: UInt16, _ offset: Int) {
            bytes[offset] = UInt8(truncatingIfNeeded: value >> 8)
            bytes[offset + 1] = UInt8(truncatingIfNeeded: value)
        }
        func put32(_ value: UInt32, _ offset: Int) {
            for i in 0..<4 { bytes[offset + i] = UInt8(truncatingIfNeeded: value >> (24 - 8 * i)) }
        }
        put16(signature, 0); put16(version, 2); put32(0x2000, 4)
        put32(blockSize, 40); put32(total, 44); put32(free, 48)
        return bytes
    }

    func testKnownHeaderUsesBigEndianAndAccurateByteCounts() throws {
        let parsed = try HFSHeaderParser.parse(syntheticHeader())
        XCTAssertEqual(parsed.format, "HFS+")
        XCTAssertEqual(parsed.attributes, 0x2000)
        XCTAssertTrue(parsed.hasJournalFlag)
        XCTAssertFalse(parsed.hasContentProtectionFlag)
        XCTAssertEqual(parsed.declaredBytes, 409_600)
        XCTAssertEqual(parsed.reportedFreeBytes, 102_400)
    }

    func testContentProtectionFlagIsReported() throws {
        var bytes = syntheticHeader()
        bytes[4] |= 0x40
        let parsed = try HFSHeaderParser.parse(bytes)
        XCTAssertTrue(parsed.hasContentProtectionFlag)
        XCTAssertTrue(parsed.hasJournalFlag)
    }

    func testHFSXAndInvalidSignaturesAndVersions() throws {
        XCTAssertEqual(try HFSHeaderParser.parse(syntheticHeader(signature: 0x4858, version: 5)).format, "HFSX")
        XCTAssertThrowsError(try HFSHeaderParser.parse(syntheticHeader(signature: 0x4244)))
        XCTAssertThrowsError(try HFSHeaderParser.parse(syntheticHeader(signature: 0x4858, version: 4)))
        XCTAssertThrowsError(try HFSHeaderParser.parse(Array(syntheticHeader().dropLast())))
    }

    func testInvalidGeometryIsRejected() {
        for size: UInt32 in [0, 511, 1025] {
            XCTAssertThrowsError(try HFSHeaderParser.parse(syntheticHeader(blockSize: size)))
        }
        XCTAssertThrowsError(try HFSHeaderParser.parse(syntheticHeader(total: 0, free: 0)))
        XCTAssertThrowsError(try HFSHeaderParser.parse(syntheticHeader(total: 100, free: 101)))
        XCTAssertThrowsError(try HFSHeaderParser.parse(syntheticHeader(blockSize: 512, total: 2, free: 0)))
    }

    func testByteCountsUse64BitArithmetic() throws {
        let header = try HFSHeaderParser.parse(syntheticHeader(blockSize: 4096, total: 14_819_755, free: 14_620_357))
        XCTAssertEqual(header.declaredBytes, 60_701_716_480)
        XCTAssertEqual(header.reportedFreeBytes, 59_884_982_272)
        let extreme = try HFSHeaderParser.parse(syntheticHeader(blockSize: 0x80000000, total: UInt32.max, free: 0))
        XCTAssertEqual(extreme.declaredBytes, 9_223_372_034_707_292_160)
    }

    func testSavedPrefixAndUntrustedFileKinds() throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: false)
        defer { try? FileManager.default.removeItem(at: directory) }
        let file = directory.appendingPathComponent("prefix.bin")
        try Data([UInt8](repeating: 0, count: 1024) + syntheticHeader()).write(to: file)
        XCTAssertEqual(try SavedFile.readPrimaryHeader(at: file.path).freeBlocks, 25)
        let link = directory.appendingPathComponent("link")
        try FileManager.default.createSymbolicLink(at: link, withDestinationURL: file)
        XCTAssertThrowsError(try SavedFile.readPrimaryHeader(at: link.path))
        XCTAssertThrowsError(try SavedFile.readPrimaryHeader(at: directory.path))
        XCTAssertThrowsError(try SavedFile.readPrimaryHeader(at: "/dev/null"))
        let fifo = directory.appendingPathComponent("fifo")
        XCTAssertEqual(mkfifo(fifo.path, 0o600), 0)
        XCTAssertThrowsError(try SavedFile.readPrimaryHeader(at: fifo.path))
        try Data(repeating: 0, count: 1535).write(to: file)
        XCTAssertThrowsError(try SavedFile.readPrimaryHeader(at: file.path))
    }
}
