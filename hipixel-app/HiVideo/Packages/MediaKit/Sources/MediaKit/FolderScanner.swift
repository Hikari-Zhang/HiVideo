// FolderScanner.swift — MediaKit
// 后台增量文件夹扫描器

import Foundation
import GRDB

// MARK: - FolderScanner

/// 后台扫描文件夹，将新视频文件写入数据库
/// 增量：已存在的文件跳过（按 file_url 唯一约束）
public final class FolderScanner: Sendable {

    private let db: DatabaseQueue

    // 支持的视频扩展名
    private static let videoExtensions: Set<String> = [
        "mp4", "m4v", "mkv", "mov", "avi", "wmv", "flv",
        "webm", "ts", "m2ts", "mts", "mpg", "mpeg", "rmvb", "rm",
    ]

    public init(db: DatabaseQueue) {
        self.db = db
    }

    // MARK: - Scan

    /// 扫描指定目录（递归），将新文件批量写入数据库
    public func scan(_ url: URL) async {
        guard url.isFileURL else { return }

        let files = collectVideoFiles(in: url)
        guard !files.isEmpty else { return }

        // 取已有路径集合（用于增量判断）
        let existingPaths: Set<String>
        do {
            existingPaths = try await db.read { db in
                let paths = try String.fetchAll(db, sql: "SELECT file_url FROM media_items")
                return Set(paths)
            }
        } catch {
            print("[FolderScanner] Failed to load existing paths: \(error)")
            return
        }

        // 过滤新文件
        let newFiles = files.filter { !existingPaths.contains($0.path) }
        guard !newFiles.isEmpty else { return }

        // 批量提取元数据 + 写入（每批 20 个，避免内存压力）
        let batchSize = 20
        for batch in stride(from: 0, to: newFiles.count, by: batchSize) {
            let end = min(batch + batchSize, newFiles.count)
            let batchFiles = Array(newFiles[batch..<end])
            await processBatch(batchFiles)
        }

        // 更新 watch_folder 扫描时间
        do {
            try await db.write { db in
                try db.execute(
                    sql: "UPDATE watch_folders SET last_scanned_at = ? WHERE path = ?",
                    arguments: [Date().timeIntervalSince1970, url.path]
                )
            }
        } catch {
            print("[FolderScanner] Failed to update scan time: \(error)")
        }
    }

    // MARK: - Private

    private func processBatch(_ files: [URL]) async {
        // 1. 先批量插入占位记录（title-only，元数据为空），UI 立即响应
        var placeholders: [MediaItem] = []
        for fileURL in files {
            let fileSize = (try? FileManager.default.attributesOfItem(atPath: fileURL.path)[.size] as? Int64) ?? 0
            placeholders.append(MediaItem(
                fileURL: fileURL.path,
                title: fileURL.deletingPathExtension().lastPathComponent,
                fileSize: fileSize,
                addedAt: Date().timeIntervalSince1970
            ))
        }
        do {
            try await db.write { db in
                for item in placeholders {
                    try item.insertAndFetch(db, onConflict: .ignore)
                }
            }
        } catch {
            print("[FolderScanner] Batch insert error: \(error)")
        }

        // 2. 后台逐一提取元数据并更新（不阻塞扫描进度）
        for (idx, fileURL) in files.enumerated() {
            let itemID = placeholders[idx].id
            Task.detached(priority: .background) { [db] in
                let meta = await MetadataExtractor.extract(from: fileURL)
                do {
                    try await db.write { db in
                        try db.execute(sql: """
                            UPDATE media_items
                            SET duration=?, width=?, height=?, codec=?, file_size=?
                            WHERE id=?
                            """,
                            arguments: [meta.duration, meta.width, meta.height,
                                        meta.codec, meta.fileSize, itemID]
                        )
                    }
                    // 缩略图
                    if let path = await ThumbnailGenerator.generate(for: fileURL, itemID: itemID) {
                        try await db.write { db in
                            try db.execute(sql: "UPDATE media_items SET thumbnail_path=? WHERE id=?",
                                           arguments: [path, itemID])
                        }
                    }
                } catch {
                    print("[FolderScanner] Metadata update error: \(error)")
                }
            }
        }
    }

    private func collectVideoFiles(in url: URL) -> [URL] {
        guard let enumerator = FileManager.default.enumerator(
            at: url,
            includingPropertiesForKeys: [.isRegularFileKey, .fileSizeKey],
            options: [.skipsHiddenFiles, .skipsPackageDescendants]
        ) else { return [] }

        var result: [URL] = []
        for case let fileURL as URL in enumerator {
            let ext = fileURL.pathExtension.lowercased()
            guard Self.videoExtensions.contains(ext) else { continue }
            guard (try? fileURL.resourceValues(forKeys: [.isRegularFileKey]).isRegularFile) == true else { continue }
            result.append(fileURL)
        }
        return result
    }
}
