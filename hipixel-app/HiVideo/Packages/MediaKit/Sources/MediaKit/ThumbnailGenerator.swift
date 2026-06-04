// ThumbnailGenerator.swift — MediaKit
// 使用 AVAssetImageGenerator 后台生成视频缩略图

import Foundation
import AVFoundation
import AppKit

// MARK: - ThumbnailGenerator

public enum ThumbnailGenerator {

    /// 缩略图存储目录
    private static var thumbnailsDirectory: URL {
        let support = FileManager.default
            .urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("HiVideo/Thumbnails", isDirectory: true)
        try? FileManager.default.createDirectory(at: support, withIntermediateDirectories: true)
        return support
    }

    // MARK: - Generate

    /// 为视频生成缩略图，返回本地路径
    /// - Parameters:
    ///   - url: 视频文件 URL
    ///   - itemID: MediaItem.id，用于命名缩略图文件
    ///   - at: 截帧时间点，默认取 10% 处
    public static func generate(for url: URL, itemID: String, at fraction: Double = 0.1) async -> String? {
        let destURL = thumbnailsDirectory.appendingPathComponent("\(itemID).jpg")

        if FileManager.default.fileExists(atPath: destURL.path) {
            return destURL.path
        }

        // MKV / AVI / TS 等容器 AVFoundation 不支持，直接走 ffmpeg
        let ext = url.pathExtension.lowercased()
        let avUnsupported: Set<String> = ["mkv", "avi", "ts", "m2ts", "mts", "rmvb", "rm", "wmv", "flv"]

        if avUnsupported.contains(ext) {
            return await generateWithFFmpeg(url: url, destURL: destURL, fraction: fraction)
        }

        // 其他格式先尝试 AVFoundation
        let result = await generateWithAVFoundation(url: url, destURL: destURL, fraction: fraction)
        if result != nil { return result }

        // AVFoundation 失败则 ffmpeg 兜底
        return await generateWithFFmpeg(url: url, destURL: destURL, fraction: fraction)
    }

    // MARK: - AVFoundation（MP4 / MOV / M4V）

    private static func generateWithAVFoundation(url: URL, destURL: URL, fraction: Double) async -> String? {
        let asset = AVURLAsset(url: url)
        let generator = AVAssetImageGenerator(asset: asset)
        generator.appliesPreferredTrackTransform = true
        generator.maximumSize = CGSize(width: 320, height: 480)
        generator.requestedTimeToleranceBefore = CMTime(seconds: 3, preferredTimescale: 600)
        generator.requestedTimeToleranceAfter  = CMTime(seconds: 3, preferredTimescale: 600)

        let duration: Double
        do {
            let cmDur = try await asset.load(.duration)
            duration = cmDur.seconds.isFinite && cmDur.seconds > 0 ? cmDur.seconds : 30
        } catch {
            return nil
        }

        let targetTime = CMTime(seconds: duration * max(0.05, min(fraction, 0.9)),
                                preferredTimescale: 600)
        do {
            let (cgImage, _) = try await generator.image(at: targetTime)
            return try saveJPEG(cgImage: cgImage, to: destURL)
        } catch {
            return nil
        }
    }

    // MARK: - ffmpeg（MKV / AVI / TS 等所有格式）

    private static func generateWithFFmpeg(url: URL, destURL: URL, fraction: Double) async -> String? {
        return await withCheckedContinuation { (cont: CheckedContinuation<String?, Never>) in
            Task.detached(priority: .background) {
                guard let ffmpeg = findExecutable("ffmpeg") else {
                    print("[ThumbnailGenerator] ffmpeg not found — install via: brew install ffmpeg")
                    cont.resume(returning: nil)
                    return
                }

                // 先用 ffprobe 取时长（秒），然后截取 fraction 处的帧
                let duration = ffprobeDuration(url: url)
                let seekSec  = duration > 0 ? duration * max(0.05, min(fraction, 0.9)) : 10.0
                let seekStr  = String(format: "%.2f", seekSec)

                let proc = Process()
                proc.executableURL = URL(fileURLWithPath: ffmpeg)
                proc.arguments = [
                    "-ss", seekStr,          // 先 seek（快速）
                    "-i", url.path,
                    "-vframes", "1",         // 只取一帧
                    "-vf", "scale=320:-1",   // 宽度 320，高度等比
                    "-q:v", "3",             // JPEG 质量（1-31，越小越好）
                    "-y",                    // 覆盖已有文件
                    destURL.path,
                ]
                // 静默 ffmpeg 输出
                proc.standardOutput = FileHandle.nullDevice
                proc.standardError  = FileHandle.nullDevice

                do {
                    try proc.run()
                    proc.waitUntilExit()
                    if proc.terminationStatus == 0,
                       FileManager.default.fileExists(atPath: destURL.path) {
                        cont.resume(returning: destURL.path)
                    } else {
                        cont.resume(returning: nil)
                    }
                } catch {
                    print("[ThumbnailGenerator] ffmpeg exec error: \(error)")
                    cont.resume(returning: nil)
                }
            }
        }
    }

    // MARK: - Helpers

    private static func saveJPEG(cgImage: CGImage, to url: URL) throws -> String {
        let nsImage = NSImage(cgImage: cgImage,
                              size: NSSize(width: cgImage.width, height: cgImage.height))
        guard let tiffData = nsImage.tiffRepresentation,
              let bitmap   = NSBitmapImageRep(data: tiffData),
              let jpegData = bitmap.representation(using: .jpeg,
                                                   properties: [.compressionFactor: 0.85])
        else { throw CocoaError(.fileWriteUnknown) }
        try jpegData.write(to: url)
        return url.path
    }

    private static func findExecutable(_ name: String) -> String? {
        let candidates = [
            "/opt/homebrew/bin/\(name)",
            "/usr/local/bin/\(name)",
            "/usr/bin/\(name)",
        ]
        return candidates.first { FileManager.default.isExecutableFile(atPath: $0) }
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
        let out = String(data: pipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8)?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return Double(out) ?? 0
    }

    // MARK: - Batch

    /// 批量生成缩略图（后台，不阻塞）
    public static func generateBatch(items: [(id: String, url: URL)]) async {
        await withTaskGroup(of: Void.self) { group in
            for item in items {
                group.addTask(priority: .background) {
                    _ = await generate(for: item.url, itemID: item.id)
                }
            }
        }
    }
}
