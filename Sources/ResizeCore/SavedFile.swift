// SPDX-License-Identifier: MIT
import Foundation
#if canImport(Darwin)
import Darwin
#else
import Glibc
#endif

public enum SavedFileError: Error {
    case openFailed
    case notRegularFile
    case readFailed
    case changedDuringRead
    case duplicateFixture
}

/// Identity is used only to reject the same file supplied as multiple inputs.
public struct SavedFileIdentity: Hashable {
    public let device: UInt64
    public let inode: UInt64
}

public struct SavedFileSnapshot {
    public let bytes: [UInt8]
    public let identity: SavedFileIdentity
}

/// Opens a saved regular file without following the last path component.
/// The input may be a bounded volume prefix rather than a complete disk image.
public enum SavedFile {
    public static func readPrimaryHeader(at path: String) throws -> HFSHeader {
        return try HFSHeaderParser.parse(readRange(at: path, offset: 1024, count: 512).bytes)
    }

    /// Reads a saved logical block which begins at byte zero of a regular file.
    public static func readHeaderBlock(at path: String, blockBytes: Int) throws -> [UInt8] {
        return try snapshotHeaderBlock(at: path, blockBytes: blockBytes).bytes
    }

    public static func snapshotHeaderBlock(at path: String, blockBytes: Int) throws -> SavedFileSnapshot {
        guard blockBytes >= 512 && blockBytes <= 65536 && blockBytes.nonzeroBitCount == 1 else {
            throw SavedFileError.readFailed
        }
        return try readRange(at: path, offset: 0, count: blockBytes)
    }

    /// Reads a complete saved fixture with a strict byte limit.
    public static func readFixture(at path: String, maximumBytes: Int = 1_048_576) throws -> [UInt8] {
        return try snapshotFixture(at: path, maximumBytes: maximumBytes).bytes
    }

    public static func snapshotFixture(at path: String, maximumBytes: Int = 1_048_576) throws -> SavedFileSnapshot {
        guard maximumBytes > 0 && maximumBytes <= 1_048_576 else { throw SavedFileError.readFailed }
        return try readRange(at: path, offset: 0, count: nil, maximumBytes: maximumBytes)
    }

    public static func requireDistinct(_ snapshots: [SavedFileSnapshot]) throws {
        guard Set(snapshots.map(\.identity)).count == snapshots.count else {
            throw SavedFileError.duplicateFixture
        }
    }

    private static func readRange(at path: String, offset: off_t, count: Int?,
                                  maximumBytes: Int = 1_048_576) throws -> SavedFileSnapshot {
        let fd = open(path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK)
        guard fd >= 0 else { throw SavedFileError.openFailed }
        defer { _ = close(fd) }
        var before = stat()
        guard fstat(fd, &before) == 0 else { throw SavedFileError.readFailed }
        guard (before.st_mode & mode_t(S_IFMT)) == mode_t(S_IFREG) else {
            throw SavedFileError.notRegularFile
        }
        let requested: Int
        if let count = count { requested = count }
        else {
            guard before.st_size > 0 && before.st_size <= maximumBytes else { throw SavedFileError.readFailed }
            requested = Int(before.st_size)
        }
        var data = [UInt8](repeating: 0, count: requested)
        var cursor = 0
        while cursor < data.count {
            let remaining = data.count - cursor
            let bytesRead = data.withUnsafeMutableBytes { raw in
                pread(fd, raw.baseAddress!.advanced(by: cursor), remaining,
                      offset + off_t(cursor))
            }
            if bytesRead < 0 && errno == EINTR { continue }
            guard bytesRead > 0 else { throw SavedFileError.readFailed }
            cursor += bytesRead
        }
        var after = stat()
        guard fstat(fd, &after) == 0 else { throw SavedFileError.readFailed }
        #if canImport(Darwin)
        let stableTimes = before.st_mtimespec.tv_sec == after.st_mtimespec.tv_sec &&
            before.st_mtimespec.tv_nsec == after.st_mtimespec.tv_nsec &&
            before.st_ctimespec.tv_sec == after.st_ctimespec.tv_sec &&
            before.st_ctimespec.tv_nsec == after.st_ctimespec.tv_nsec
        #else
        let stableTimes = before.st_mtim.tv_sec == after.st_mtim.tv_sec &&
            before.st_mtim.tv_nsec == after.st_mtim.tv_nsec &&
            before.st_ctim.tv_sec == after.st_ctim.tv_sec &&
            before.st_ctim.tv_nsec == after.st_ctim.tv_nsec
        #endif
        guard before.st_dev == after.st_dev && before.st_ino == after.st_ino &&
            before.st_size == after.st_size && stableTimes else {
            throw SavedFileError.changedDuringRead
        }
        return SavedFileSnapshot(bytes: data, identity: SavedFileIdentity(
            device: UInt64(truncatingIfNeeded: before.st_dev), inode: UInt64(truncatingIfNeeded: before.st_ino)))
    }
}
