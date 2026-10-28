// SPDX-License-Identifier: MIT
/// An in-memory fixture model informed by the offline 13G36 trace. It does not
/// inspect a header, determine chunk limits, access storage or authorize writes.
public struct HypotheticalLwVMReconciliation: Equatable {
    public static let entryCount = 1024
    public static let freeMarker: UInt16 = 0xf111

    public struct Allocation: Equatable {
        public let slot: Int
        public let owner: Int
        public let index: Int
    }

    public enum FixtureError: Error, Equatable {
        case invalidEntryCount
        case invalidLimits
        case ownerWithoutLimit
        case unsupportedEntryBits
        case duplicateIndex
        case gappedIndices
        case insufficientFreeMarkers
    }

    public let entries: [UInt16]
    public let releasedSlots: [Int]
    public let allocations: [Allocation]

    /// The map and limits are caller-supplied fixtures. Unlike the trace's
    /// maximum-index check, this model requires every input owner's complete
    /// index sequence to be contiguous and unique, including released indices.
    public init(entries: [UInt16], limits: [Int]) throws {
        guard entries.count == Self.entryCount else { throw FixtureError.invalidEntryCount }
        guard (1...8).contains(limits.count),
              limits.allSatisfy({ (0...Self.entryCount).contains($0) }),
              limits.reduce(0, +) <= Self.entryCount else { throw FixtureError.invalidLimits }
        var indices = Array(repeating: Set<Int>(), count: limits.count)
        for entry in entries {
            let owner = Int(entry >> 12)
            if owner == 15 { continue }
            guard owner < limits.count else { throw FixtureError.ownerWithoutLimit }
            guard entry & 0x0c00 == 0 else { throw FixtureError.unsupportedEntryBits }
            guard indices[owner].insert(Int(entry & 0x03ff)).inserted else {
                throw FixtureError.duplicateIndex
            }
        }
        for ownerIndices in indices {
            if let maximum = ownerIndices.max(), ownerIndices.count != maximum + 1 {
                throw FixtureError.gappedIndices
            }
        }
        var output = entries
        var released: [Int] = []
        for (slot, entry) in entries.enumerated() {
            let owner = Int(entry >> 12)
            if owner == 15 { continue }
            if Int(entry & 0x03ff) >= limits[owner] {
                output[slot] = Self.freeMarker
                released.append(slot)
            }
        }
        var allocations: [Allocation] = []
        var cursor = 0
        for owner in limits.indices {
            let retainedCount = min(indices[owner].count, limits[owner])
            for index in retainedCount..<limits[owner] {
                while cursor < Self.entryCount && output[cursor] != Self.freeMarker { cursor += 1 }
                guard cursor < Self.entryCount else { throw FixtureError.insufficientFreeMarkers }
                output[cursor] = UInt16(owner << 12 | index)
                allocations.append(Allocation(slot: cursor, owner: owner, index: index))
                cursor += 1
            }
        }
        self.entries = output
        self.releasedSlots = released
        self.allocations = allocations
    }
}
