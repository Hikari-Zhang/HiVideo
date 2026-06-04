// Player.swift — PlaybackKit
// 播放器协议定义，所有后端（VideoToolbox、AVPlayer fallback）都实现此协议
// Phase 1: HiVideoPlayer 实现（FFmpeg + VideoToolbox + Metal）

import Foundation
import CoreMedia
import Combine

// MARK: - PlayerState

/// 播放器状态枚举
public enum PlaybackStatus: Equatable {
    case idle           // 未加载
    case loading        // 加载中
    case ready          // 已就绪（可播放）
    case playing        // 播放中
    case paused         // 已暂停
    case buffering      // 缓冲中
    case ended          // 播放完毕
    case error(String)  // 错误

    public static func == (lhs: PlaybackStatus, rhs: PlaybackStatus) -> Bool {
        switch (lhs, rhs) {
        case (.idle, .idle), (.loading, .loading), (.ready, .ready),
             (.playing, .playing), (.paused, .paused),
             (.buffering, .buffering), (.ended, .ended):
            return true
        case (.error(let a), .error(let b)):
            return a == b
        default:
            return false
        }
    }
}

// MARK: - Player Protocol

/// 播放器核心协议
/// 所有播放后端（VideoToolbox、AVPlayer fallback）必须实现此协议
public protocol Player: AnyObject {
    // 状态
    var status: PlaybackStatus { get }
    var currentTime: CMTime { get }
    var duration: CMTime { get }
    var volume: Float { get set }
    var isMuted: Bool { get set }
    var rate: Float { get set }                 // 播放速率，1.0 = 正常
    var videoSize: CGSize { get }
    var hdrMetadata: HDRMetadata? { get }

    // Publishers
    var statusPublisher: AnyPublisher<PlaybackStatus, Never> { get }
    var timePublisher: AnyPublisher<CMTime, Never> { get }

    // 生命周期
    func load(_ url: URL) async
    func play()
    func pause()
    func stop()
    func seek(to time: CMTime) async

    // 轨道
    var audioTracks: [TrackInfo] { get }
    var subtitleTracks: [TrackInfo] { get }
    var selectedAudioTrack: Int { get set }
    var selectedSubtitleTrack: Int? { get set }  // nil = 关闭字幕
}

// MARK: - Supporting Types

/// 轨道信息（音频/字幕）
public struct TrackInfo: Identifiable, Sendable {
    public let id: Int
    public let language: String     // ISO 639-1 语言码，如 "zh", "en", "ja"
    public let title: String        // 轨道名称
    public let codec: String        // 编码格式
    public let isDefault: Bool

    public init(id: Int, language: String, title: String, codec: String, isDefault: Bool = false) {
        self.id = id
        self.language = language
        self.title = title
        self.codec = codec
        self.isDefault = isDefault
    }
}

/// HDR 元数据
public struct HDRMetadata: Sendable {
    public enum HDRFormat: String, Sendable {
        case hdr10 = "HDR10"
        case dolbyVision = "Dolby Vision"
        case hlg = "HLG"
        case hdr10Plus = "HDR10+"
    }
    public let format: HDRFormat
    public let maxLuminance: Float?   // nits
    public let minLuminance: Float?   // nits

    public init(format: HDRFormat, maxLuminance: Float? = nil, minLuminance: Float? = nil) {
        self.format = format
        self.maxLuminance = maxLuminance
        self.minLuminance = minLuminance
    }
}

// MARK: - Convenience Extensions

extension Player {
    /// 播放进度 0.0 – 1.0
    public var progress: Double {
        guard duration.seconds > 0 else { return 0 }
        return currentTime.seconds / duration.seconds
    }

    /// 是否正在播放
    public var isPlaying: Bool { status == .playing }

    /// 切换播放/暂停
    public func togglePlayPause() {
        if isPlaying { pause() } else { play() }
    }

    /// 快进/快退
    public func skip(by seconds: Double) async {
        let newTime = CMTime(seconds: currentTime.seconds + seconds, preferredTimescale: 600)
        let clamped = CMTimeMaximum(CMTimeMinimum(newTime, duration), .zero)
        await seek(to: clamped)
    }
}
