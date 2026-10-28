// SPDX-License-Identifier: MIT
import Foundation
#if canImport(Darwin)
import Darwin
#else
import Glibc
#endif

public struct HFSImageHeaderSummary: Equatable, Codable {
    public let primary: HFSHeader
    public let fileBytes: UInt64
    public let alternateHeaderOffset: UInt64
    public var trailingBytes: UInt64 { fileBytes - primary.declaredBytes }
}

public enum HFSImageHeaderError: Error, Equatable {
    case openFailed
    case notRegularFile
    case incompleteImage
    case overlappingHeaders
    case readFailed
    case geometryMismatch
    case changedDuringRead
}

/// Reads the primary and filesystem-end alternate headers from one saved file.
/// Selected geometry checks leave allocation, journal and catalog checks to fsck.
public enum HFSImageHeaders {
    public static func inspect(at path: String) throws -> HFSImageHeaderSummary {
        let fd = open(path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK)
        guard fd >= 0 else { throw HFSImageHeaderError.openFailed }
        defer { _ = close(fd) }
        var before = stat()
        guard fstat(fd, &before) == 0 else { throw HFSImageHeaderError.readFailed }
        guard before.st_mode & mode_t(S_IFMT) == mode_t(S_IFREG) else {
            throw HFSImageHeaderError.notRegularFile
        }
        guard before.st_size >= 1536 else { throw HFSImageHeaderError.incompleteImage }
        func header(at offset: UInt64) throws -> HFSHeader {
            guard offset <= UInt64(Int64.max) - 512 else { throw HFSImageHeaderError.readFailed }
            var bytes = [UInt8](repeating: 0, count: 512)
            var cursor = 0
            while cursor < bytes.count {
                let count = bytes.withUnsafeMutableBytes { raw in
                    pread(fd, raw.baseAddress!.advanced(by: cursor), 512 - cursor, off_t(offset) + off_t(cursor))
                }
                if count < 0 && errno == EINTR { continue }
                guard count > 0 else { throw HFSImageHeaderError.readFailed }
                cursor += count
            }
            return try HFSHeaderParser.parse(bytes)
        }
        let primary = try header(at: 1024)
        guard primary.declaredBytes >= 2560 else { throw HFSImageHeaderError.overlappingHeaders }
        guard primary.declaredBytes <= UInt64(before.st_size) else {
            throw HFSImageHeaderError.incompleteImage
        }
        let offset = primary.declaredBytes - 1024
        let alternate = try header(at: offset)
        guard alternate.format == primary.format, alternate.version == primary.version,
              alternate.allocationBlockBytes == primary.allocationBlockBytes,
              alternate.totalBlocks == primary.totalBlocks else {
            throw HFSImageHeaderError.geometryMismatch
        }
        var after = stat()
        guard fstat(fd, &after) == 0 else { throw HFSImageHeaderError.readFailed }
        #if canImport(Darwin)
        let sameTimes = before.st_mtimespec.tv_sec == after.st_mtimespec.tv_sec &&
            before.st_mtimespec.tv_nsec == after.st_mtimespec.tv_nsec &&
            before.st_ctimespec.tv_sec == after.st_ctimespec.tv_sec &&
            before.st_ctimespec.tv_nsec == after.st_ctimespec.tv_nsec
        #else
        let sameTimes = before.st_mtim.tv_sec == after.st_mtim.tv_sec &&
            before.st_mtim.tv_nsec == after.st_mtim.tv_nsec &&
            before.st_ctim.tv_sec == after.st_ctim.tv_sec &&
            before.st_ctim.tv_nsec == after.st_ctim.tv_nsec
        #endif
        guard before.st_dev == after.st_dev && before.st_ino == after.st_ino &&
              before.st_size == after.st_size && sameTimes else {
            throw HFSImageHeaderError.changedDuringRead
        }
        return HFSImageHeaderSummary(primary: primary, fileBytes: UInt64(before.st_size),
                                     alternateHeaderOffset: offset)
    }
}
