// SPDX-License-Identifier: MIT
/// An inclusive block range in caller-supplied synthetic geometry. This type
/// does not choose space, read LwVM, or authorize a partition-table change.
public struct BlockRange: Equatable {
    public let first: UInt64
    public let count: UInt64
    public let lastInclusive: UInt64

    public enum RangeError: Error, Equatable {
        case empty
        case outOfBounds
        case overflow
    }

    public init(first: UInt64, count: UInt64, mediaBlockCount: UInt64) throws {
        guard count > 0 else { throw RangeError.empty }
        let (last, overflow) = first.addingReportingOverflow(count - 1)
        guard !overflow else { throw RangeError.overflow }
        guard last < mediaBlockCount else { throw RangeError.outOfBounds }
        self.first = first
        self.count = count
        self.lastInclusive = last
    }
}
