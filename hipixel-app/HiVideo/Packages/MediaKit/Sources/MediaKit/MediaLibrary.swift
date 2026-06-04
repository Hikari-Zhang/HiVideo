// MediaLibrary.swift — MediaKit
// 媒体库主入口：增删查、续播记录

import Foundation
import GRDB
import Combine

// MARK: - MediaLibrary

@MainActor
public final class MediaLibrary: ObservableObject {

    // MARK: - Published State

    @Published public private(set) var items: [MediaItem] = []
    @Published public private(set) var watchFolders: [WatchFolder] = []
    @Published public private(set) var isScanning: Bool = false

    // MARK: - Private

    private let db: DatabaseQueue
    private var observation: AnyDatabaseCancellable?

    // MARK: - Init

    public init(db: DatabaseQueue) {
        self.db = db
        Task { await reload() }
        startObservation()
    }

    /// 便利初始化（使用默认路径）
    public convenience init() throws {
        let db = try AppDatabase.makeDatabaseQueue()
        self.init(db: db)
    }

    // MARK: - Read

    public func reload() async {
        do {
            let (loadedItems, loadedFolders) = try await db.read { db in
                let items = try MediaItem
                    .order(Column("added_at").desc)
                    .fetchAll(db)
                let folders = try WatchFolder.fetchAll(db)
                return (items, folders)
            }
            items = loadedItems
            watchFolders = loadedFolders
        } catch {
            print("[MediaLibrary] reload error: \(error)")
        }
    }

    /// 最近播放（有续播位置 或 最近播放时间）
    public var recentlyPlayed: [MediaItem] {
        items
            .filter { $0.lastPlayedAt != nil }
            .sorted { ($0.lastPlayedAt ?? 0) > ($1.lastPlayedAt ?? 0) }
            .prefix(10)
            .map { $0 }
    }

    /// 在看中（续播位置 > 5%）
    public var inProgress: [MediaItem] {
        items.filter { item in
            item.duration > 0 && item.resumePosition / item.duration > 0.05 && item.resumePosition / item.duration < 0.95
        }
    }

    // MARK: - Write

    /// 添加单个文件到媒体库
    @discardableResult
    public func add(fileURL: URL) async throws -> MediaItem {
        var item = MediaItem(
            fileURL: fileURL.path,
            title: fileURL.deletingPathExtension().lastPathComponent,
            addedAt: Date().timeIntervalSince1970
        )

        // 先插入占位记录让 UI 立即显示
        try await db.write { db in
            // INSERT OR IGNORE：避免重复
            if try MediaItem.filter(Column("file_url") == fileURL.path).fetchOne(db) == nil {
                try item.insert(db)
            }
        }
        await reload()

        // 后台提取元数据，完成后更新记录
        Task.detached(priority: .utility) { [weak self] in
            guard let self else { return }
            let meta = await MetadataExtractor.extract(from: fileURL)
            await self.updateMetadata(for: item.id, meta: meta, url: fileURL)
        }

        return item
    }

    /// 更新已有条目的元数据（提取完成后回调）
    public func updateMetadata(for id: String, meta: VideoMetadata, url: URL) async {
        do {
            try await db.write { db in
                try db.execute(sql: """
                    UPDATE media_items
                    SET duration=?, width=?, height=?, codec=?, file_size=?
                    WHERE id=?
                    """,
                    arguments: [meta.duration, meta.width, meta.height, meta.codec, meta.fileSize, id]
                )
            }
            // 缩略图也在此时生成
            let thumbPath = await ThumbnailGenerator.generate(for: url, itemID: id)
            if let path = thumbPath {
                try await db.write { db in
                    try db.execute(sql: "UPDATE media_items SET thumbnail_path=? WHERE id=?",
                                   arguments: [path, id])
                }
            }
        } catch {
            print("[MediaLibrary] updateMetadata error: \(error)")
        }
    }

    /// 添加监视文件夹并立即扫描
    public func addWatchFolder(_ url: URL) async throws {
        let folder = WatchFolder(path: url.path)
        try await db.write { db in
            try folder.insert(db)
        }
        await reload()
        await scanFolder(url)
    }

    /// 从媒体库移除（不删除文件）
    public func remove(item: MediaItem) async throws {
        try await db.write { db in
            try item.delete(db)
        }
        await reload()
    }

    /// 删除监视文件夹
    public func removeWatchFolder(_ folder: WatchFolder) async throws {
        try await db.write { db in
            try folder.delete(db)
        }
        await reload()
    }

    // MARK: - Resume Position

    /// 更新续播位置
    public func updateResumePosition(for item: MediaItem, position: Double) async {
        var updated = item
        updated.resumePosition = position
        updated.lastPlayedAt = Date().timeIntervalSince1970
        try? await db.write { db in
            try updated.update(db)
        }
        // 更新本地缓存（不 reload 整个库，性能更好）
        if let idx = items.firstIndex(where: { $0.id == item.id }) {
            items[idx] = updated
        }
    }

    // MARK: - Scan

    public func scanFolder(_ url: URL) async {
        isScanning = true
        defer { Task { @MainActor in self.isScanning = false } }

        let scanner = FolderScanner(db: db)
        await scanner.scan(url)
        await reload()
    }

    public func rescanAll() async {
        for folder in watchFolders {
            await scanFolder(URL(fileURLWithPath: folder.path))
        }
    }

    // MARK: - Private: Live Observation

    private func startObservation() {
        let observation = ValueObservation.tracking { db in
            try MediaItem.order(Column("added_at").desc).fetchAll(db)
        }
        self.observation = observation.start(in: db, scheduling: .async(onQueue: .main)) { [weak self] error in
            print("[MediaLibrary] observation error: \(error)")
        } onChange: { [weak self] items in
            self?.items = items
        }
    }
}
