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

        return await withCheckedContinuation { (continuation: CheckedContinuation<String?, Never>) in
            Task.detached(priority: .background) {
                let asset = AVURLAsset(url: url)
                let generator = AVAssetImageGenerator(asset: asset)
                generator.appliesPreferredTrackTransform = true
                generator.maximumSize = CGSize(width: 320, height: 480)

                // 目标时间：duration × fraction
                let duration: CMTime
                do {
                    duration = try await asset.load(.duration)
                } catch {
                    continuation.resume(returning: nil)
                    return
                }

                let targetTime = CMTime(
                    seconds: duration.seconds * max(0.05, min(fraction, 0.9)),
                    preferredTimescale: 600
                )

                // 使用 async/await 版本（macOS 13+）
                do {
                    let (cgImage, _) = try await generator.image(at: targetTime)

                    let nsImage = NSImage(cgImage: cgImage, size: NSSize(width: cgImage.width, height: cgImage.height))
                    guard let tiffData = nsImage.tiffRepresentation,
                          let bitmap = NSBitmapImageRep(data: tiffData),
                          let jpegData = bitmap.representation(using: .jpeg, properties: [.compressionFactor: 0.85]) else {
                        continuation.resume(returning: nil)
                        return
                    }

                    do {
                        try jpegData.write(to: destURL)
                        continuation.resume(returning: destURL.path)
                    } catch {
                        print("[ThumbnailGenerator] Write failed: \(error)")
                        continuation.resume(returning: nil)
                    }
                } catch {
                    continuation.resume(returning: nil)
                }
            }
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
