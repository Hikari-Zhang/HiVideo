// MetadataExtractor.swift — MediaKit
// 使用 AVFoundation 提取视频元数据（分辨率、时长、编码、文件大小）

import Foundation
import AVFoundation

// MARK: - VideoMetadata

public struct VideoMetadata: Sendable {
    public let duration: Double     // 秒
    public let width: Int
    public let height: Int
    public let codec: String        // "h264", "hevc", "av1" 等
    public let fileSize: Int64      // 字节
    public let frameRate: Double    // fps
}

// MARK: - MetadataExtractor

public enum MetadataExtractor {

    /// 异步提取视频文件元数据
    public static func extract(from url: URL) async -> VideoMetadata {
        let fileSize = (try? FileManager.default.attributesOfItem(atPath: url.path)[.size] as? Int64) ?? 0

        let asset = AVURLAsset(url: url, options: [AVURLAssetPreferPreciseDurationAndTimingKey: false])

        // 时长
        let duration: Double
        do {
            let cmDuration = try await asset.load(.duration)
            duration = cmDuration.seconds
        } catch {
            duration = 0
        }

        // 视频轨道
        var width = 0, height = 0, codec = "", frameRate = 0.0
        do {
            let tracks = try await asset.loadTracks(withMediaType: .video)
            if let track = tracks.first {
                let size = try await track.load(.naturalSize)
                width = Int(size.width)
                height = Int(size.height)
                let fps = try await track.load(.nominalFrameRate)
                frameRate = Double(fps)

                // 编码格式
                if let formatDescs = try? await track.load(.formatDescriptions),
                   let desc = formatDescs.first {
                    let fourCC = CMFormatDescriptionGetMediaSubType(desc)
                    codec = fourCCToString(fourCC)
                }
            }
        } catch {
            print("[MetadataExtractor] Track load error for \(url.lastPathComponent): \(error)")
        }

        return VideoMetadata(
            duration: duration,
            width: width,
            height: height,
            codec: codec,
            fileSize: fileSize,
            frameRate: frameRate
        )
    }

    // MARK: - Private Helpers

    private static func fourCCToString(_ fourCC: FourCharCode) -> String {
        let bytes = [
            UInt8((fourCC >> 24) & 0xFF),
            UInt8((fourCC >> 16) & 0xFF),
            UInt8((fourCC >>  8) & 0xFF),
            UInt8( fourCC        & 0xFF),
        ]
        let raw = String(bytes: bytes, encoding: .ascii)?.trimmingCharacters(in: .whitespaces) ?? ""
        switch raw.lowercased() {
        case "avc1", "avc3":  return "h264"
        case "hvc1", "hev1":  return "hevc"
        case "av01":          return "av1"
        case "vp09":          return "vp9"
        case "vp08":          return "vp8"
        case "ap4h", "apch":  return "prores"
        default:              return raw.isEmpty ? "unknown" : raw.lowercased()
        }
    }
}
