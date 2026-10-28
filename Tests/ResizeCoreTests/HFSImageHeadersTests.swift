// SPDX-License-Identifier: MIT
import Foundation
import XCTest
@testable import ResizeCore
#if canImport(Darwin)
import Darwin
#else
import Glibc
#endif

final class HFSImageHeadersTests: XCTestCase {
    func header(blocks: UInt32 = 16, free: UInt32 = 4) -> [UInt8] {
        var bytes = [UInt8](repeating: 0, count: 512)
        bytes[0] = 0x48; bytes[1] = 0x58; bytes[3] = 5
        for (offset, value) in [(40, UInt32(512)), (44, blocks), (48, free)] {
            for n in 0..<4 { bytes[offset + n] = UInt8(truncatingIfNeeded: value >> (24 - n * 8)) }
        }
        return bytes
    }

    func fixture(totalBytes: Int = 8192, alternate: [UInt8]? = nil) throws -> (URL, URL) {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: false)
        addTeardownBlock { try FileManager.default.removeItem(at: directory) }
        let file = directory.appendingPathComponent("saved.hfs")
        var image = [UInt8](repeating: 0, count: totalBytes)
        image.replaceSubrange(1024..<1536, with: header())
        if totalBytes >= 8192 {
            image.replaceSubrange(7168..<7680, with: alternate ?? header())
        }
        try Data(image).write(to: file)
        return (directory, file)
    }

    func testCompleteImageUsesFilesystemEndAndPreservesAllInputBytes() throws {
        let (_, file) = try fixture()
        let before = try Data(contentsOf: file)
        let result = try HFSImageHeaders.inspect(at: file.path)
        XCTAssertEqual(result.primary.format, "HFSX")
        XCTAssertEqual(result.primary.declaredBytes, 8192)
        XCTAssertEqual(result.alternateHeaderOffset, 7168)
        XCTAssertEqual(result.trailingBytes, 0)
        XCTAssertEqual(try Data(contentsOf: file), before)
    }

    func testLargerBackingFileIsAllowedAfterFilesystemOnlyShrink() throws {
        let (_, file) = try fixture(totalBytes: 16384)
        let result = try HFSImageHeaders.inspect(at: file.path)
        XCTAssertEqual(result.primary.declaredBytes, 8192)
        XCTAssertEqual(result.fileBytes, 16384)
        XCTAssertEqual(result.trailingBytes, 8192)
    }

    func testPrimaryOnlyPrefixCannotPassCompleteImageCheck() throws {
        let (_, file) = try fixture(totalBytes: 1536)
        XCTAssertNoThrow(try SavedFile.readPrimaryHeader(at: file.path))
        XCTAssertThrowsError(try HFSImageHeaders.inspect(at: file.path)) {
            XCTAssertEqual($0 as? HFSImageHeaderError, .incompleteImage)
        }
    }

    func testDifferentAlternateGeometryIsRejected() throws {
        let (_, file) = try fixture(alternate: header(blocks: 15))
        XCTAssertThrowsError(try HFSImageHeaders.inspect(at: file.path)) {
            XCTAssertEqual($0 as? HFSImageHeaderError, .geometryMismatch)
        }
    }

    func testStaleAlternateCountersDoNotBecomeAGeometryMismatch() throws {
        let (_, file) = try fixture(alternate: header(free: 3))
        XCTAssertNoThrow(try HFSImageHeaders.inspect(at: file.path))
    }

    func testSymlinksDeviceFilesDirectoriesAndFifosAreRejected() throws {
        let (directory, file) = try fixture()
        let link = directory.appendingPathComponent("alias")
        try FileManager.default.createSymbolicLink(at: link, withDestinationURL: file)
        let fifo = directory.appendingPathComponent("fifo")
        XCTAssertEqual(mkfifo(fifo.path, 0o600), 0)
        for path in [link.path, directory.path, fifo.path, "/dev/null"] {
            XCTAssertThrowsError(try HFSImageHeaders.inspect(at: path))
        }
    }

    func testBadAlternateHeaderIsRejected() throws {
        let (_, file) = try fixture(alternate: [UInt8](repeating: 0, count: 512))
        XCTAssertThrowsError(try HFSImageHeaders.inspect(at: file.path))
    }
}
