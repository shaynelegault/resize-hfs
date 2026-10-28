// SPDX-License-Identifier: MIT
import XCTest
@testable import ResizeCore

final class BlockRangeTests: XCTestCase {
    func testInclusiveLastUsesCountMinusOne() throws {
        XCTAssertEqual(try BlockRange(first: 4096, count: 8192, mediaBlockCount: 12_288).lastInclusive, 12_287)
        XCTAssertEqual(try BlockRange(first: 99, count: 1, mediaBlockCount: 100).lastInclusive, 99)
    }

    func testEmptyOverflowAndEndOutsideMediaFail() {
        XCTAssertThrowsError(try BlockRange(first: 0, count: 0, mediaBlockCount: 100))
        XCTAssertThrowsError(try BlockRange(first: 99, count: 2, mediaBlockCount: 100))
        XCTAssertThrowsError(try BlockRange(first: UInt64.max - 1, count: 3, mediaBlockCount: UInt64.max))
        XCTAssertThrowsError(try BlockRange(first: 0, count: 1, mediaBlockCount: 0))
    }
}
