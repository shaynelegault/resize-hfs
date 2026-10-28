// SPDX-License-Identifier: MIT
import XCTest
@testable import ResizeCore

final class HypotheticalLwVMReconciliationTests: XCTestCase {
    private let free: UInt16 = 0xf111
    private func blank(_ marker: UInt16 = 0xf111) -> [UInt16] {
        Array(repeating: marker, count: 1024)
    }

    func testOneChunkShrinkPreservesUnrelatedMarkersAndInput() throws {
        var map = blank(0xf3ff)
        for i in 0..<41 { map[i] = UInt16(i) }
        for i in 0..<905 { map[41 + i] = 0x1000 | UInt16(i) }
        map[946] = 0xf000
        map[947] = free
        let original = map
        let result = try HypotheticalLwVMReconciliation(entries: map, limits: [41, 904])
        XCTAssertEqual(map, original)
        XCTAssertEqual(result.releasedSlots, [945])
        XCTAssertEqual(result.entries[945], free)
        XCTAssertEqual(result.entries[946], 0xf000)
        XCTAssertEqual(result.entries[947], free)
        XCTAssertEqual(result.entries[948], 0xf3ff)
        XCTAssertTrue(result.allocations.isEmpty)
    }

    func testAllocatesOnlyExactFreeMarkerAndReusesReleasedSlot() throws {
        var map = blank(0xf3ff)
        map[0] = 0
        map[1] = 1
        map[2] = 0xf000
        let result = try HypotheticalLwVMReconciliation(entries: map, limits: [1, 1])
        XCTAssertEqual(result.releasedSlots, [1])
        XCTAssertEqual(result.entries[1], 0x1000)
        XCTAssertEqual(result.entries[2], 0xf000)
        XCTAssertEqual(result.allocations, [.init(slot: 1, owner: 1, index: 0)])
    }

    func testNoExactFreeMarkerFails() {
        var map = blank(0xf3ff)
        map[0] = 0
        let original = map
        XCTAssertThrowsError(try HypotheticalLwVMReconciliation(entries: map, limits: [2])) {
            XCTAssertEqual($0 as? HypotheticalLwVMReconciliation.FixtureError, .insufficientFreeMarkers)
        }
        XCTAssertEqual(map, original)
    }

    func testFullMapAndMultipleOwnerAllocationOrder() throws {
        let full = try HypotheticalLwVMReconciliation(entries: blank(), limits: [1024])
        XCTAssertEqual(full.allocations.count, 1024)
        XCTAssertEqual(full.entries[1023], 0x03ff)

        var map = blank(0xffff)
        map[0] = 0
        map[1] = 1
        map[2] = free
        let result = try HypotheticalLwVMReconciliation(entries: map, limits: [1, 2])
        XCTAssertEqual(result.releasedSlots, [1])
        XCTAssertEqual(result.allocations, [
            .init(slot: 1, owner: 1, index: 0),
            .init(slot: 2, owner: 1, index: 1)
        ])
        XCTAssertEqual(result.entries[3], 0xffff)
    }

    func testDuplicateAndGapEvenOutsideLimitFail() {
        var map = blank()
        map[0] = 0; map[1] = 1; map[2] = 1
        XCTAssertThrowsError(try HypotheticalLwVMReconciliation(entries: map, limits: [1])) {
            XCTAssertEqual($0 as? HypotheticalLwVMReconciliation.FixtureError, .duplicateIndex)
        }
        map[2] = 3
        XCTAssertThrowsError(try HypotheticalLwVMReconciliation(entries: map, limits: [1])) {
            XCTAssertEqual($0 as? HypotheticalLwVMReconciliation.FixtureError, .gappedIndices)
        }
    }

    func testInvalidFixturesFailClosed() {
        XCTAssertThrowsError(try HypotheticalLwVMReconciliation(entries: [], limits: [1]))
        XCTAssertThrowsError(try HypotheticalLwVMReconciliation(entries: blank(), limits: []))
        XCTAssertThrowsError(try HypotheticalLwVMReconciliation(entries: blank(), limits: [1024, 1]))
        XCTAssertThrowsError(try HypotheticalLwVMReconciliation(entries: blank(), limits: [-1]))
        var map = blank(); map[0] = 0x1000
        XCTAssertThrowsError(try HypotheticalLwVMReconciliation(entries: map, limits: [1]))
        map[0] = 0x0400
        XCTAssertThrowsError(try HypotheticalLwVMReconciliation(entries: map, limits: [1]))
    }
}
