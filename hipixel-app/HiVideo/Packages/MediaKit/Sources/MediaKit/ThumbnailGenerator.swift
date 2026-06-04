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

        // 已存在则直接返回
        if FileManager.default.fileExists(atPath: destURL.path) {
            return destURL.path
        }

        let asset = AVURLAsset(url: url)
        let generator = AVAssetImageGenerator(asset: asset)
        generator.appliesPreferredTrackTransform = true
        generator.maximumSize = CGSize(width: 320, height: 480)
        // 允许使用最近帧，提高 MKV 兼容性
        generator.requestedTimeToleranceBefore = CMTime(seconds: 3, preferredTimescale: 600)
        generator.requestedTimeToleranceAfter  = CMTime(seconds: 3, preferredTimescale: 600)

        // 先加载时长
        let duration: Double
        do {
            let cmDur = try await asset.load(.duration)
            duration = cmDur.seconds.isFinite && cmDur.seconds > 0 ? cmDur.seconds : 30
        } catch {
            // 无法读取时长时截第 5 秒
            duration = 30
        }

        let targetTime = CMTime(
            seconds: duration * max(0.05, min(fraction, 0.9)),
            preferredTimescale: 600
        )

        do {
            let (cgImage, _) = try await generator.image(at: targetTime)
            let nsImage = NSImage(cgImage: cgImage,
                                  size: NSSize(width: cgImage.width, height: cgImage.height))
            guard let tiffData  = nsImage.tiffRepresentation,
                  let bitmap    = NSBitmapImageRep(data: tiffData),
                  let jpegData  = bitmap.representation(using: .jpeg,
                                                        properties: [.compressionFactor: 0.85])
            else { return nil }

            try jpegData.write(to: destURL)
            return destURL.path
        } catch {
            print("[ThumbnailGenerator] Failed for \(url.lastPathComponent): \(error)")
            return nil
        }
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
