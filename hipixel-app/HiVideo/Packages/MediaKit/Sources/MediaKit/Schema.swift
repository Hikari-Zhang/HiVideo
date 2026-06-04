// Schema.swift — MediaKit
// GRDB 数据模型定义

import Foundation
import GRDB

// MARK: - MediaItem

/// 媒体库中的视频条目
public struct MediaItem: Identifiable, Codable, FetchableRecord, PersistableRecord, Sendable {
    public var id: String                  // UUID 字符串
    public var fileURL: String             // 文件绝对路径
    public var title: String               // 显示标题（文件名去扩展名）
    public var duration: Double            // 总时长（秒）
    public var width: Int                  // 视频宽度（像素）
    public var height: Int                 // 视频高度（像素）
    public var codec: String               // 视频编码（h264/hevc/av1 等）
    public var fileSize: Int64             // 文件大小（字节）
    public var resumePosition: Double      // 续播位置（秒），0 = 未看
    public var addedAt: TimeInterval       // 添加时间（Unix 时间戳）
    public var lastPlayedAt: TimeInterval? // 最后播放时间，nil = 未看过
    public var thumbnailPath: String?      // 缩略图本地路径

    // 数据库列映射
    public static let databaseTableName = "media_items"

    enum CodingKeys: String, CodingKey {
        case id
        case fileURL = "file_url"
        case title
        case duration
        case width, height, codec
        case fileSize = "file_size"
        case resumePosition = "resume_position"
        case addedAt = "added_at"
        case lastPlayedAt = "last_played_at"
        case thumbnailPath = "thumbnail_path"
    }

    public init(
        id: String = UUID().uuidString,
        fileURL: String,
        title: String,
        duration: Double = 0,
        width: Int = 0,
        height: Int = 0,
        codec: String = "",
        fileSize: Int64 = 0,
        resumePosition: Double = 0,
        addedAt: TimeInterval = Date().timeIntervalSince1970,
        lastPlayedAt: TimeInterval? = nil,
        thumbnailPath: String? = nil
    ) {
        self.id = id
        self.fileURL = fileURL
        self.title = title
        self.duration = duration
        self.width = width
        self.height = height
        self.codec = codec
        self.fileSize = fileSize
        self.resumePosition = resumePosition
        self.addedAt = addedAt
        self.lastPlayedAt = lastPlayedAt
        self.thumbnailPath = thumbnailPath
    }

    /// 文件 URL（从 fileURL 字符串还原）
    public var url: URL { URL(fileURLWithPath: fileURL) }

    /// 分辨率描述（如 "4K HDR"、"1080p"）
    public var resolutionLabel: String {
        switch height {
        case 2160...: return "4K"
        case 1440...: return "2K"
        case 1080...: return "1080p"
        case 720...:  return "720p"
        case 480...:  return "480p"
        default:      return "\(height)p"
        }
    }

    /// 时长格式化（HH:MM:SS）
    public var durationLabel: String {
        let s = Int(duration)
        let h = s / 3600, m = (s % 3600) / 60, sec = s % 60
        if h > 0 { return String(format: "%d:%02d:%02d", h, m, sec) }
        return String(format: "%02d:%02d", m, sec)
    }
}

// MARK: - WatchFolder

/// 监视文件夹记录
public struct WatchFolder: Identifiable, Codable, FetchableRecord, PersistableRecord, Sendable {
    public var id: String
    public var path: String                // 文件夹绝对路径
    public var lastScannedAt: TimeInterval?

    public static let databaseTableName = "watch_folders"

    enum CodingKeys: String, CodingKey {
        case id
        case path
        case lastScannedAt = "last_scanned_at"
    }

    public init(id: String = UUID().uuidString, path: String, lastScannedAt: TimeInterval? = nil) {
        self.id = id
        self.path = path
        self.lastScannedAt = lastScannedAt
    }
}

// MARK: - Database Migrations

public struct AppDatabase {

    public static func makeDatabaseQueue(at path: String? = nil) throws -> DatabaseQueue {
        let dbPath: String
        if let path {
            dbPath = path
        } else {
            let support = FileManager.default
                .urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
                .appendingPathComponent("HiVideo", isDirectory: true)
            try FileManager.default.createDirectory(at: support, withIntermediateDirectories: true)
            dbPath = support.appendingPathComponent("library.db").path
        }

        let queue = try DatabaseQueue(path: dbPath)
        try migrate(queue)
        return queue
    }

    private static func migrate(_ db: DatabaseQueue) throws {
        var migrator = DatabaseMigrator()

        migrator.registerMigration("v1_initial") { db in
            try db.create(table: "media_items") { t in
                t.column("id", .text).primaryKey()
                t.column("file_url", .text).notNull().unique()
                t.column("title", .text).notNull()
                t.column("duration", .double).notNull().defaults(to: 0)
                t.column("width", .integer).notNull().defaults(to: 0)
                t.column("height", .integer).notNull().defaults(to: 0)
                t.column("codec", .text).notNull().defaults(to: "")
                t.column("file_size", .integer).notNull().defaults(to: 0)
                t.column("resume_position", .double).notNull().defaults(to: 0)
                t.column("added_at", .double).notNull()
                t.column("last_played_at", .double)
                t.column("thumbnail_path", .text)
            }

            try db.create(table: "watch_folders") { t in
                t.column("id", .text).primaryKey()
                t.column("path", .text).notNull().unique()
                t.column("last_scanned_at", .double)
            }

            // 索引：按添加时间倒序查询
            try db.create(index: "idx_media_added_at", on: "media_items", columns: ["added_at"])
            try db.create(index: "idx_media_last_played", on: "media_items", columns: ["last_played_at"])
        }

        try migrator.migrate(db)
    }
}
