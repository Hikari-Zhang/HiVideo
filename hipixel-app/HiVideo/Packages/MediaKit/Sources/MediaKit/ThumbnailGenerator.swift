// ThumbnailGenerator.swift — MediaKit
// 视频缩略图生成：QuickLook（系统级，支持所有格式）+ ffmpeg 兜底

import Foundation
import AppKit
import QuickLookThumbnailing

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

        // 已存在直接返回
        if FileManager.default.fileExists(atPath: destURL.path) {
            return destURL.path
        }

        // 1. 优先用系统 QuickLook（支持所有 macOS 能播的格式，包括大部分 MKV）
        if let path = await generateWithQuickLook(url: url, destURL: destURL) {
            return path
        }

        // 2. QuickLook 失败再用 ffmpeg
        return await generateWithFFmpeg(url: url, destURL: destURL, fraction: fraction)
    }

    // MARK: - QuickLook

    private static func generateWithQuickLook(url: URL, destURL: URL) async -> String? {
        let size = CGSize(width: 320, height: 480)
        let request = QLThumbnailGenerator.Request(
            fileAt: url,
            size: size,
            scale: 1.0,
            representationTypes: .thumbnail
        )

        return await withCheckedContinuation { cont in
            QLThumbnailGenerator.shared.generateBestRepresentation(for: request) { thumb, error in
                guard let thumb, error == nil else {
                    cont.resume(returning: nil)
                    return
                }
                let nsImage = thumb.nsImage
                guard let tiffData = nsImage.tiffRepresentation,
                      let bitmap   = NSBitmapImageRep(data: tiffData),
                      let jpegData = bitmap.representation(using: .jpeg,
                                                           properties: [.compressionFactor: 0.85])
                else {
                    cont.resume(returning: nil)
                    return
                }
                do {
                    try jpegData.write(to: destURL)
                    cont.resume(returning: destURL.path)
                } catch {
                    cont.resume(returning: nil)
                }
            }
        }
    }

    // MARK: - ffmpeg fallback

    private static func generateWithFFmpeg(url: URL, destURL: URL, fraction: Double) async -> String? {
        guard let ffmpeg = findExecutable("ffmpeg") else { return nil }

        return await withCheckedContinuation { cont in
            Task.detached(priority: .background) {
                let duration = await ffprobeDuration(url: url)
                let seekSec  = duration > 0 ? duration * max(0.05, min(fraction, 0.9)) : 10.0

                let proc = Process()
                proc.executableURL = URL(fileURLWithPath: ffmpeg)
                proc.arguments = [
                    "-ss", String(format: "%.2f", seekSec),
                    "-i", url.path,
                    "-vframes", "1",
                    "-vf", "scale=320:-1",
                    "-q:v", "3", "-y",
                    destURL.path,
                ]
                proc.standardOutput = FileHandle.nullDevice
                proc.standardError  = FileHandle.nullDevice
                do {
                    try proc.run(); proc.waitUntilExit()
                    if proc.terminationStatus == 0,
                       FileManager.default.fileExists(atPath: destURL.path) {
                        cont.resume(returning: destURL.path)
                    } else {
                        cont.resume(returning: nil)
                    }
                } catch {
                    cont.resume(returning: nil)
                }
            }
        }
    }

    // MARK: - Batch

    public static func generateBatch(items: [(id: String, url: URL)]) async {
        await withTaskGroup(of: Void.self) { group in
            for item in items {
                group.addTask(priority: .background) {
                    _ = await generate(for: item.url, itemID: item.id)
                }
            }
        }
    }

    // MARK: - Helpers

    private static func findExecutable(_ name: String) -> String? {
        ["/opt/homebrew/bin/\(name)", "/usr/local/bin/\(name)", "/usr/bin/\(name)"]
            .first { FileManager.default.isExecutableFile(atPath: $0) }
    }

    private static func ffprobeDuration(url: URL) async -> Double {
        guard let ffprobe = findExecutable("ffprobe") else { return 0 }
        return await withCheckedContinuation { cont in
            let proc = Process()
            proc.executableURL = URL(fileURLWithPath: ffprobe)
            proc.arguments = ["-v", "quiet",
                               "-show_entries", "format=duration",
                               "-of", "default=noprint_wrappers=1:nokey=1",
                               url.path]
            let pipe = Pipe()
            proc.standardOutput = pipe
            proc.standardError  = FileHandle.nullDevice
            try? proc.run(); proc.waitUntilExit()
            let out = String(data: pipe.fileHandleForReading.readDataToEndOfFile(),
                             encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            cont.resume(returning: Double(out) ?? 0)
        }
    }
}
