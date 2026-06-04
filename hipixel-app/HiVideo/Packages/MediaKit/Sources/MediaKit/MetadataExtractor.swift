// MetadataExtractor.swift — MediaKit
// 视频元数据提取：AVFoundation（MP4/MOV）+ ffprobe 兜底（MKV/AVI/TS 等）

import Foundation
import AVFoundation

// MARK: - VideoMetadata

public struct VideoMetadata: Sendable {
    public let duration: Double
    public let width: Int
    public let height: Int
    public let codec: String
    public let fileSize: Int64
    public let frameRate: Double
}

// MARK: - MetadataExtractor

public enum MetadataExtractor {

    // AVFoundation 不支持的容器，直接走 ffprobe
    private static let ffprobeOnly: Set<String> = [
        "mkv", "avi", "ts", "m2ts", "mts", "rmvb", "rm", "wmv", "flv", "webm",
    ]

    public static func extract(from url: URL) async -> VideoMetadata {
        let fileSize = (try? FileManager.default
            .attributesOfItem(atPath: url.path)[.size] as? Int64) ?? 0

        let ext = url.pathExtension.lowercased()

        // 已知不支持的格式直接 ffprobe，避免 AVFoundation 内部报错
        if ffprobeOnly.contains(ext) {
            return await extractWithFFprobe(url: url, fileSize: fileSize)
        }

        // MP4 / MOV / M4V 等先走 AVFoundation
        let av = await extractWithAVFoundation(url: url, fileSize: fileSize)

        // 如果 AVFoundation 拿到了有效数据就返回
        if av.duration > 0 && av.width > 0 {
            return av
        }

        // 否则 ffprobe 补充
        let ffp = await extractWithFFprobe(url: url, fileSize: fileSize)
        return VideoMetadata(
            duration:  av.duration  > 0 ? av.duration  : ffp.duration,
            width:     av.width     > 0 ? av.width     : ffp.width,
            height:    av.height    > 0 ? av.height    : ffp.height,
            codec:     av.codec.isEmpty ? ffp.codec     : av.codec,
            fileSize:  fileSize,
            frameRate: av.frameRate > 0 ? av.frameRate : ffp.frameRate
        )
    }

    // MARK: - AVFoundation

    private static func extractWithAVFoundation(url: URL, fileSize: Int64) async -> VideoMetadata {
        let asset = AVURLAsset(url: url,
                               options: [AVURLAssetPreferPreciseDurationAndTimingKey: false])

        let loaded: Bool = await withCheckedContinuation { cont in
            asset.loadValuesAsynchronously(forKeys: ["tracks", "duration"]) {
                let s = asset.statusOfValue(forKey: "duration", error: nil)
                cont.resume(returning: s == .loaded)
            }
        }
        guard loaded else {
            return VideoMetadata(duration: 0, width: 0, height: 0,
                                 codec: "", fileSize: fileSize, frameRate: 0)
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

        return VideoMetadata(duration: duration, width: width, height: height,
                             codec: codec, fileSize: fileSize, frameRate: frameRate)
    }

    // MARK: - ffprobe

    private static func extractWithFFprobe(url: URL, fileSize: Int64) async -> VideoMetadata {
        return await withCheckedContinuation { cont in
            Task.detached(priority: .utility) {
                guard let ffprobe = findExecutable("ffprobe") else {
                    cont.resume(returning: VideoMetadata(
                        duration: 0, width: 0, height: 0,
                        codec: "", fileSize: fileSize, frameRate: 0))
                    return
                }

                let proc = Process()
                proc.executableURL = URL(fileURLWithPath: ffprobe)
                proc.arguments = [
                    "-v", "quiet",
                    "-print_format", "json",
                    "-show_streams", "-show_format",
                    url.path,
                ]
                let pipe = Pipe()
                proc.standardOutput = pipe
                proc.standardError  = FileHandle.nullDevice

                var duration = 0.0, width = 0, height = 0
                var codec = "", frameRate = 0.0

                do {
                    try proc.run()
                    proc.waitUntilExit()
                    let data = pipe.fileHandleForReading.readDataToEndOfFile()
                    if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                        if let fmt = json["format"] as? [String: Any],
                           let dur = fmt["duration"] as? String {
                            duration = Double(dur) ?? 0
                        }
                        if let streams = json["streams"] as? [[String: Any]] {
                            for s in streams where (s["codec_type"] as? String) == "video" {
                                width  = s["width"]  as? Int ?? 0
                                height = s["height"] as? Int ?? 0
                                codec  = s["codec_name"] as? String ?? ""
                                let fpsStr = s["r_frame_rate"] as? String ?? "0/1"
                                let parts  = fpsStr.split(separator: "/")
                                if parts.count == 2,
                                   let n = Double(parts[0]), let d = Double(parts[1]), d > 0 {
                                    frameRate = n / d
                                }
                                break
                            }
                        }
                    }
                } catch {
                    print("[MetadataExtractor] ffprobe error: \(error)")
                }

                cont.resume(returning: VideoMetadata(
                    duration: duration, width: width, height: height,
                    codec: codec, fileSize: fileSize, frameRate: frameRate))
            }
        }
    }

    // MARK: - Helpers

    private static func findExecutable(_ name: String) -> String? {
        ["/opt/homebrew/bin/\(name)", "/usr/local/bin/\(name)", "/usr/bin/\(name)"]
            .first { FileManager.default.isExecutableFile(atPath: $0) }
    }

    private static func fourCCToString(_ fourCC: FourCharCode) -> String {
        let bytes = [
            UInt8((fourCC >> 24) & 0xFF), UInt8((fourCC >> 16) & 0xFF),
            UInt8((fourCC >>  8) & 0xFF), UInt8( fourCC        & 0xFF),
        ]
        let raw = String(bytes: bytes, encoding: .ascii)?
            .trimmingCharacters(in: .whitespaces) ?? ""
        switch raw.lowercased() {
        case "avc1", "avc3": return "h264"
        case "hvc1", "hev1": return "hevc"
        case "av01":         return "av1"
        case "vp09":         return "vp9"
        case "ap4h", "apch": return "prores"
        default:             return raw.isEmpty ? "unknown" : raw.lowercased()
        }
    }
}
