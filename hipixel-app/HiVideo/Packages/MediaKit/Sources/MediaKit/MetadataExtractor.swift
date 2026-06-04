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
        // 文件大小（直接读文件属性，不依赖 AVFoundation）
        let fileSize = (try? FileManager.default
            .attributesOfItem(atPath: url.path)[.size] as? Int64) ?? 0

        // 对 MKV / AVI / TS 等容器使用 AVURLAsset，但部分格式 AVFoundation 支持有限
        // 先尝试 AVURLAsset，如果 duration == 0 再用 ffprobe 兜底
        let asset = AVURLAsset(
            url: url,
            options: [AVURLAssetPreferPreciseDurationAndTimingKey: false]
        )

        // 等待资产可读
        let status = await withCheckedContinuation { (cont: CheckedContinuation<AVKeyValueStatus, Never>) in
            asset.loadValuesAsynchronously(forKeys: ["playable", "tracks", "duration"]) {
                let s = asset.statusOfValue(forKey: "duration", error: nil)
                cont.resume(returning: s)
            }
        }

        guard status == .loaded else {
            // AVFoundation 无法读取（如部分 MKV），返回用 ffprobe 提取的结果
            return await extractWithFFprobe(url: url, fileSize: fileSize)
        }

        let duration = asset.duration.seconds.isFinite ? asset.duration.seconds : 0
        var width = 0, height = 0, codec = "", frameRate = 0.0

        if let track = asset.tracks(withMediaType: .video).first {
            let size = track.naturalSize.applying(track.preferredTransform)
            width  = Int(abs(size.width))
            height = Int(abs(size.height))
            frameRate = Double(track.nominalFrameRate)

            if let desc = track.formatDescriptions.first {
                let fourCC = CMFormatDescriptionGetMediaSubType(desc as! CMFormatDescription)
                codec = fourCCToString(fourCC)
            }
        }

        // 如果 AVFoundation 拿不到有效分辨率，再用 ffprobe 补充
        if width == 0 || duration == 0 {
            let fb = await extractWithFFprobe(url: url, fileSize: fileSize)
            return VideoMetadata(
                duration: duration > 0 ? duration : fb.duration,
                width:    width  > 0  ? width   : fb.width,
                height:   height > 0  ? height  : fb.height,
                codec:    codec.isEmpty ? fb.codec : codec,
                fileSize: fileSize,
                frameRate: frameRate > 0 ? frameRate : fb.frameRate
            )
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

    // MARK: - ffprobe fallback

    /// 用系统 ffprobe 提取元数据（适用于 AVFoundation 不支持的容器）
    private static func extractWithFFprobe(url: URL, fileSize: Int64) async -> VideoMetadata {
        return await withCheckedContinuation { cont in
            Task.detached(priority: .utility) {
                var duration = 0.0, width = 0, height = 0, codec = "", frameRate = 0.0

                // ffprobe 路径：系统 PATH 或 Homebrew 常见位置
                let ffprobePaths = ["/opt/homebrew/bin/ffprobe", "/usr/local/bin/ffprobe", "ffprobe"]
                var ffprobePath: String? = nil
                for path in ffprobePaths {
                    if path == "ffprobe" {
                        if let resolved = try? Process().executableURL.flatMap({ _ in
                            URL(fileURLWithPath: "/usr/bin/which")
                        }) { _ = resolved }
                        // 用 which 查找
                        let which = Process()
                        which.executableURL = URL(fileURLWithPath: "/usr/bin/which")
                        which.arguments = ["ffprobe"]
                        let pipe = Pipe()
                        which.standardOutput = pipe
                        try? which.run()
                        which.waitUntilExit()
                        let out = String(data: pipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8)?
                            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
                        if !out.isEmpty { ffprobePath = out; break }
                    } else if FileManager.default.fileExists(atPath: path) {
                        ffprobePath = path; break
                    }
                }

                if let ffprobe = ffprobePath {
                    let proc = Process()
                    proc.executableURL = URL(fileURLWithPath: ffprobe)
                    proc.arguments = [
                        "-v", "quiet",
                        "-print_format", "json",
                        "-show_streams",
                        "-show_format",
                        url.path
                    ]
                    let pipe = Pipe()
                    proc.standardOutput = pipe
                    try? proc.run()
                    proc.waitUntilExit()

                    let data = pipe.fileHandleForReading.readDataToEndOfFile()
                    if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                        // 时长
                        if let fmt = json["format"] as? [String: Any],
                           let durStr = fmt["duration"] as? String {
                            duration = Double(durStr) ?? 0
                        }
                        // 视频流
                        if let streams = json["streams"] as? [[String: Any]] {
                            for s in streams where (s["codec_type"] as? String) == "video" {
                                width      = s["width"]  as? Int ?? 0
                                height     = s["height"] as? Int ?? 0
                                codec      = s["codec_name"] as? String ?? ""
                                let fpsStr = s["r_frame_rate"] as? String ?? "0/1"
                                let parts  = fpsStr.split(separator: "/")
                                if parts.count == 2,
                                   let num = Double(parts[0]), let den = Double(parts[1]), den > 0 {
                                    frameRate = num / den
                                }
                                break
                            }
                        }
                    }
                }

                cont.resume(returning: VideoMetadata(
                    duration: duration,
                    width: width,
                    height: height,
                    codec: codec,
                    fileSize: fileSize,
                    frameRate: frameRate
                ))
            }
        }
    }

    // MARK: - Helpers

    private static func fourCCToString(_ fourCC: FourCharCode) -> String {
        let bytes = [
            UInt8((fourCC >> 24) & 0xFF),
            UInt8((fourCC >> 16) & 0xFF),
            UInt8((fourCC >>  8) & 0xFF),
            UInt8( fourCC        & 0xFF),
        ]
        let raw = String(bytes: bytes, encoding: .ascii)?
            .trimmingCharacters(in: .whitespaces) ?? ""
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

