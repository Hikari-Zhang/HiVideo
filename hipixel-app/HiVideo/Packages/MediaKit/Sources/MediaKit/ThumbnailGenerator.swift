// ThumbnailGenerator.swift — MediaKit
// 视频缩略图生成：ffmpeg 截帧

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

    public static func generate(for url: URL, itemID: String, at fraction: Double = 0.1) async -> String? {
        let destURL = thumbnailsDirectory.appendingPathComponent("\(itemID).jpg")

        if FileManager.default.fileExists(atPath: destURL.path) {
            return destURL.path
        }

        return await Task.detached(priority: .background) {
            // 找 ffmpeg
            let candidates = ["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/usr/bin/ffmpeg"]
            guard let ffmpeg = candidates.first(where: { FileManager.default.isExecutableFile(atPath: $0) }) else {
                print("[Thumb] ❌ ffmpeg not found at \(candidates)")
                return nil
            }
            print("[Thumb] ✓ Using ffmpeg: \(ffmpeg)")

            // 用 ffprobe 获取时长（同步）
            let dur = Self.syncFFprobeDuration(url: url)
            let seek = dur > 0 ? dur * max(0.05, min(fraction, 0.9)) : 10.0
            print("[Thumb] duration=\(dur)s seek=\(seek)s file=\(url.lastPathComponent)")

            let proc = Process()
            proc.executableURL = URL(fileURLWithPath: ffmpeg)
            proc.arguments = [
                "-ss", String(format: "%.2f", seek),
                "-i", url.path,
                "-vframes", "1",
                "-vf", "scale=320:-1",
                "-q:v", "3",
                "-y",
                destURL.path,
            ]
            let errPipe = Pipe()
            proc.standardOutput = FileHandle.nullDevice
            proc.standardError  = errPipe

            do {
                try proc.run()
                proc.waitUntilExit()
                let errOut = String(data: errPipe.fileHandleForReading.readDataToEndOfFile(),
                                    encoding: .utf8) ?? ""
                let exists = FileManager.default.fileExists(atPath: destURL.path)
                let size   = (try? FileManager.default.attributesOfItem(atPath: destURL.path)[.size] as? Int) ?? 0
                print("[Thumb] exit=\(proc.terminationStatus) fileExists=\(exists) size=\(size)B")
                if !errOut.isEmpty { print("[Thumb] ffmpeg stderr: \(errOut.suffix(300))") }

                if proc.terminationStatus == 0, exists, size > 100 {
                    return destURL.path
                }
            } catch {
                print("[Thumb] Process error: \(error)")
            }
            return nil
        }.value
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

    static func findExecutable(_ name: String) -> String? {
        ["/opt/homebrew/bin/\(name)", "/usr/local/bin/\(name)", "/usr/bin/\(name)"]
            .first { FileManager.default.isExecutableFile(atPath: $0) }
    }

    private static func syncFFprobeDuration(url: URL) -> Double {
        guard let ffprobe = findExecutable("ffprobe") else { return 0 }
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: ffprobe)
        proc.arguments = ["-v", "quiet", "-show_entries", "format=duration",
                           "-of", "default=noprint_wrappers=1:nokey=1", url.path]
        let pipe = Pipe()
        proc.standardOutput = pipe
        proc.standardError  = FileHandle.nullDevice
        try? proc.run(); proc.waitUntilExit()
        let out = String(data: pipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8)?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return Double(out) ?? 0
    }
}
