// SPDX-License-Identifier: MIT
import XCTest
@testable import ResizeCore

final class FixtureResizeScenarioTests: XCTestCase {
    private let hfsType: [UInt8] = [0x00, 0x53, 0x46, 0x48, 0x00, 0x00, 0xaa, 0x11,
                                   0xaa, 0x11, 0x00, 0x30, 0x65, 0x43, 0xec, 0xac]
    private func put32(_ n: UInt32, _ i: Int, _ b: inout [UInt8]) {
        for j in 0..<4 { b[i + j] = UInt8(truncatingIfNeeded: n >> (8 * j)) }
    }
    private func put64(_ n: UInt64, _ i: Int, _ b: inout [UInt8]) {
        for j in 0..<8 { b[i + j] = UInt8(truncatingIfNeeded: n >> (8 * j)) }
    }
    private func putBE32(_ n: UInt32, _ i: Int, _ b: inout [UInt8]) {
        for j in 0..<4 { b[i + j] = UInt8(truncatingIfNeeded: n >> (8 * (3 - j))) }
    }
    private func entries() -> [UInt8] {
        var b = [UInt8](repeating: 0, count: 512)
        b[0] = 1; put64(6, 32, &b); put64(20, 40, &b)
        b.replaceSubrange(128..<144, with: hfsType)
        put64(21, 160, &b); put64(148, 168, &b)
        return b
    }
    private func header(primary: Bool, entries: [UInt8]) -> [UInt8] {
        var b = [UInt8](repeating: 0, count: 512)
        b.replaceSubrange(0..<8, with: "EFI PART".utf8)
        put32(1, 8, &b); put32(92, 12, &b)
        put64(primary ? 1 : 999, 24, &b); put64(primary ? 999 : 1, 32, &b)
        put64(3, 40, &b); put64(997, 48, &b)
        b[56] = 1; put64(primary ? 2 : 998, 72, &b)
        put32(4, 80, &b); put32(128, 84, &b)
        put32(GPTLikeHeaderDiagnostic.crc32(entries), 88, &b)
        put32(GPTLikeHeaderDiagnostic.crc32(Array(b.prefix(92))), 16, &b)
        return b
    }
    private func hfs(blocks: UInt32 = 128) -> [UInt8] {
        var b = [UInt8](repeating: 0, count: 512)
        b[0] = 0x48; b[1] = 0x58; b[3] = 5
        putBE32(512, 40, &b); putBE32(blocks, 44, &b); putBE32(80, 48, &b)
        return b
    }
    private func map() -> [UInt16] {
        var b = [UInt16](repeating: 0xf000, count: 1024)
        b[1] = 0x0000; b[2] = 0x1000; b[3] = 0x1001; b[4] = 0xf111
        return b
    }
    private func scenario(entries: [UInt8], backupEntries: [UInt8]? = nil,
                          index: Int = 1, hfsHeader: [UInt8]? = nil,
                          target: UInt64 = 32768, map: [UInt16]? = nil) throws -> FixtureResizeScenario {
        try FixtureResizeScenario(primaryHeader: header(primary: true, entries: entries),
                                  backupHeader: header(primary: false, entries: entries),
                                  primaryEntries: entries, backupEntries: backupEntries ?? entries,
                                  mediaBlockBytes: 512, mediaBlockCount: 1000,
                                  entryIndex: index, hfsHeader: hfsHeader ?? hfs(),
                                  targetBytes: target, fixtureMap: map ?? self.map(),
                                  fixtureLimits: [1, 1, 1])
    }

    func testCompleteFixtureProducesCheckedHypotheticalRangesAndChunkChanges() throws {
        let sourceMap = map()
        let result = try scenario(entries: entries(), map: sourceMap)
        XCTAssertEqual(result.table.usedCount, 2)
        XCTAssertEqual(result.volume.declaredBytes, 65536)
        XCTAssertEqual(result.geometry.reduced.first, 21)
        XCTAssertEqual(result.geometry.reduced.lastInclusive, 84)
        XCTAssertEqual(result.geometry.releasedTail.first, 85)
        XCTAssertEqual(result.geometry.releasedTail.lastInclusive, 148)
        XCTAssertEqual(result.chunkFixture.releasedSlots, [3])
        XCTAssertEqual(result.chunkFixture.allocations.first?.slot, 3)
        XCTAssertEqual(result.chunkFixture.entries[3], 0x2000)
        XCTAssertEqual(sourceMap[3], 0x1001)
    }

    func testRejectsInvalidMirrorsAndUnavailableEntry() {
        let original = entries()
        var damaged = original; damaged[160] ^= 1
        XCTAssertThrowsError(try scenario(entries: original, backupEntries: damaged))
        XCTAssertThrowsError(try scenario(entries: original, index: 4)) {
            XCTAssertEqual($0 as? FixtureResizeScenario.ScenarioError, .invalidPartitionIndex)
        }
        XCTAssertThrowsError(try scenario(entries: original, index: 2)) {
            XCTAssertEqual($0 as? FixtureResizeScenario.ScenarioError, .partitionAbsent)
        }
    }

    func testRejectsOtherPartitionTypeAndInconsistentHFSSize() {
        var nonHFS = entries(); nonHFS[128] = 1
        XCTAssertThrowsError(try scenario(entries: nonHFS)) {
            XCTAssertEqual($0 as? FixtureResizeScenario.ScenarioError, .unsupportedPartitionType)
        }
        XCTAssertThrowsError(try scenario(entries: entries(), hfsHeader: hfs(blocks: 129))) {
            XCTAssertEqual($0 as? FixtureResizeScenario.ScenarioError, .volumeExceedsPartition)
        }
        XCTAssertThrowsError(try scenario(entries: entries(), target: 65536)) {
            XCTAssertEqual($0 as? FixtureResizeScenario.ScenarioError, .targetDoesNotShrinkVolume)
        }
        XCTAssertThrowsError(try scenario(entries: entries(), target: 32769))
    }

    func testRejectsAmbiguousSyntheticChunkMap() {
        var broken = map(); broken[4] = 0x1000
        XCTAssertThrowsError(try scenario(entries: entries(), map: broken)) {
            XCTAssertEqual($0 as? HypotheticalLwVMReconciliation.FixtureError, .duplicateIndex)
        }
    }
}
