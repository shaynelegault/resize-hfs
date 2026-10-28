// SPDX-License-Identifier: MIT
import XCTest
@testable import ResizeCore

final class HypotheticalShrinkTests: XCTestCase {
    func testRetainedRangeAndReleasedTailAreInclusiveAndContiguous() throws {
        let result = try HypotheticalShrink(existingFirst: 100, existingBlockCount: 20,
                                            mediaBlockCount: 1000, mediaBlockBytes: 4096,
                                            filesystemBlockBytes: 8192, targetBytes: 12 * 4096)
        XCTAssertEqual(result.existing.lastInclusive, 119)
        XCTAssertEqual(result.reduced.first, 100)
        XCTAssertEqual(result.reduced.count, 12)
        XCTAssertEqual(result.reduced.lastInclusive, 111)
        XCTAssertEqual(result.releasedTail.first, 112)
        XCTAssertEqual(result.releasedTail.count, 8)
        XCTAssertEqual(result.releasedTail.lastInclusive, 119)
    }

    func testOneBlockRetainedAndOneBlockReleased() throws {
        let result = try HypotheticalShrink(existingFirst: 98, existingBlockCount: 2,
                                            mediaBlockCount: 100, mediaBlockBytes: 4096,
                                            filesystemBlockBytes: 4096, targetBytes: 4096)
        XCTAssertEqual(result.reduced.lastInclusive, 98)
        XCTAssertEqual(result.releasedTail.first, 99)
        XCTAssertEqual(result.releasedTail.lastInclusive, 99)
        XCTAssertEqual(result.releasedTail.count, 1)
    }

    func testLargeHypotheticalGeometryUsesFullWidthArithmetic() throws {
        let result = try HypotheticalShrink(existingFirst: 663_131, existingBlockCount: 14_819_755,
                                            mediaBlockCount: 15_482_891, mediaBlockBytes: 4096,
                                            filesystemBlockBytes: 4096,
                                            targetBytes: UInt64(20) * 1024 * 1024 * 1024)
        XCTAssertEqual(result.reduced.lastInclusive, 5_906_010)
        XCTAssertEqual(result.releasedTail.first, 5_906_011)
        XCTAssertEqual(result.releasedTail.count, 9_576_875)
        XCTAssertEqual(result.releasedTail.lastInclusive, 15_482_885)
    }

    func testRejectsZeroUnalignedAndNoSpaceTargets() {
        func calculate(_ target: UInt64, media: UInt32 = 4096, filesystem: UInt32 = 4096) throws -> HypotheticalShrink {
            try HypotheticalShrink(existingFirst: 10, existingBlockCount: 10,
                                   mediaBlockCount: 100, mediaBlockBytes: media,
                                   filesystemBlockBytes: filesystem, targetBytes: target)
        }
        XCTAssertThrowsError(try calculate(0)) { XCTAssertEqual($0 as? HypotheticalShrink.GeometryError, .emptyTarget) }
        XCTAssertThrowsError(try calculate(4096, filesystem: 8192)) { XCTAssertEqual($0 as? HypotheticalShrink.GeometryError, .misalignedTarget) }
        XCTAssertThrowsError(try calculate(512, filesystem: 512)) { XCTAssertEqual($0 as? HypotheticalShrink.GeometryError, .misalignedTarget) }
        XCTAssertThrowsError(try calculate(10 * 4096)) { XCTAssertEqual($0 as? HypotheticalShrink.GeometryError, .noReleasedSpace) }
        XCTAssertThrowsError(try calculate(11 * 4096)) { XCTAssertEqual($0 as? HypotheticalShrink.GeometryError, .noReleasedSpace) }
    }

    func testRejectsInvalidGeometryAndArithmeticOverflow() {
        XCTAssertThrowsError(try HypotheticalShrink(existingFirst: 0, existingBlockCount: 4,
                                                    mediaBlockCount: 4, mediaBlockBytes: 513,
                                                    filesystemBlockBytes: 4096, targetBytes: 4096))
        XCTAssertThrowsError(try HypotheticalShrink(existingFirst: 99, existingBlockCount: 2,
                                                    mediaBlockCount: 100, mediaBlockBytes: 4096,
                                                    filesystemBlockBytes: 4096, targetBytes: 4096))
        XCTAssertThrowsError(try HypotheticalShrink(existingFirst: UInt64.max - 1, existingBlockCount: 3,
                                                    mediaBlockCount: UInt64.max, mediaBlockBytes: 4096,
                                                    filesystemBlockBytes: 4096, targetBytes: 4096))
        XCTAssertThrowsError(try HypotheticalShrink(existingFirst: 0, existingBlockCount: UInt64.max,
                                                    mediaBlockCount: UInt64.max, mediaBlockBytes: 4096,
                                                    filesystemBlockBytes: 4096, targetBytes: 4096)) {
            XCTAssertEqual($0 as? HypotheticalShrink.GeometryError, .sizeOverflow)
        }
    }
}
