// ThumbnailGenerator.swift — MediaKit
// 视频缩略图生成：ffmpeg 截帧（最可靠，支持所有格式）

import Foundation
import AppKit

public enum ThumbnailGenerator {

    private static var thumbnailsDirectory: URL {
        let support = FileManager.default
            .urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("HiVideo/Thumbnails", isDirectory: true)
        try? FileManager.default.createDirectory(at: support, withIntermediateDirectories: true)
        return support
    }

    // MARK: - Public API

    public static func generate(for url: URL, itemID: String, at fraction: Double = 0.1) async -> String? {
        let destURL = thumbnailsDirectory.appendingPathComponent("\(itemID).jpg")

        if FileManager.default.fileExists(atPath: destURL.path) {
            return destURL.path
        }

        // ffmpeg 是最可靠的方式，支持所有格式
        return await generateWithFFmpeg(url: url, destURL: destURL, fraction: fraction)
    }

    public static func generateBatch(items: [(id: String, url: URL)]) async {
        await withTaskGroup(of: Void.self) { group in
            for item in items {
                group.addTask(priority: .background) {
                    _ = await generate(for: item.url, itemID: item.id)
                }
            }
        }
    }

    // MARK: - ffmpeg

    private static func generateWithFFmpeg(url: URL, destURL: URL, fraction: Double) async -> String? {
        guard let ffmpeg = findExecutable("ffmpeg") else {
            print("[ThumbnailGenerator] ffmpeg not found. Install: brew install ffmpeg")
            return nil
        }

        return await Task.detached(priority: .background) {
            // 先用 ffprobe 获取时长
            let duration = Self.ffprobeDuration(url: url)
            let seekSec  = duration > 0
                ? duration * max(0.05, min(fraction, 0.9))
                : 10.0

            let proc = Process()
            proc.executableURL = URL(fileURLWithPath: ffmpeg)
            proc.arguments = [
                "-ss", String(format: "%.2f", seekSec),
                "-i", url.path,
                "-vframes", "1",
                "-vf", "scale=320:-1",
                "-q:v", "3",
                "-y",
                destURL.path,
            ]
            proc.standardOutput = FileHandle.nullDevice
            proc.standardError  = FileHandle.nullDevice

            do {
                try proc.run()
                proc.waitUntilExit()
                if proc.terminationStatus == 0,
                   FileManager.default.fileExists(atPath: destURL.path) {
                    return destURL.path
                }
            } catch {
                print("[ThumbnailGenerator] ffmpeg error: \(error)")
            }
            return nil
        }.value
    }

    // MARK: - Helpers

    static func findExecutable(_ name: String) -> String? {
        ["/opt/homebrew/bin/\(name)", "/usr/local/bin/\(name)", "/usr/bin/\(name)"]
            .first { FileManager.default.isExecutableFile(atPath: $0) }
    }

    private static func ffprobeDuration(url: URL) -> Double {
        guard let ffprobe = findExecutable("ffprobe") else { return 0 }
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: ffprobe)
        proc.arguments = [
            "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            url.path,
        ]
        let pipe = Pipe()
        proc.standardOutput = pipe
        proc.standardError  = FileHandle.nullDevice
        try? proc.run()
        proc.waitUntilExit()
        let out = String(data: pipe.fileHandleForReading.readDataToEndOfFile(),
                         encoding: .utf8)?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return Double(out) ?? 0
    }
}
