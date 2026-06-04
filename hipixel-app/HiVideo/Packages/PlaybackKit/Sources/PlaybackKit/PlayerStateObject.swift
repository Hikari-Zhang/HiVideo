// PlayerState.swift — PlaybackKit
// 可观察的播放器状态，供 SwiftUI 视图绑定
// 与 HiVideoDesign/Components/PlayerControls.swift 中的 PlayerState 合并为统一状态层

import Foundation
import CoreMedia
import Combine
import SwiftUI

/// 可观察的播放器状态对象，SwiftUI 视图通过 @ObservedObject / @StateObject 使用
@MainActor
public final class PlayerStateObject: ObservableObject {

    // MARK: - Published State

    @Published public var status: PlaybackStatus = .idle
    @Published public var currentTime: Double = 0          // 秒
    @Published public var duration: Double = 0             // 秒
    @Published public var volume: Float = 1.0
    @Published public var isMuted: Bool = false
    @Published public var rate: Float = 1.0
    @Published public var isFullscreen: Bool = false
    @Published public var isEnhancementEnabled: Bool = false
    @Published public var videoSize: CGSize = .zero
    @Published public var hdrMetadata: HDRMetadata? = nil
    @Published public var audioTracks: [TrackInfo] = []
    @Published public var subtitleTracks: [TrackInfo] = []
    @Published public var selectedAudioTrack: Int = 0
    @Published public var selectedSubtitleTrack: Int? = nil

    // MARK: - Computed

    public var progress: Double {
        guard duration > 0 else { return 0 }
        return currentTime / duration
    }

    public var isPlaying: Bool { status == .playing }
    public var isLoaded: Bool { status == .ready || status == .playing || status == .paused || status == .buffering }

    // MARK: - Internal Player Reference

    private weak var player: (any Player)?
    private var cancellables = Set<AnyCancellable>()

    public init() {}

    // MARK: - Bind to Player

    /// 绑定到播放器实例，自动同步状态
    public func bind(to player: any Player) {
        self.player = player

        player.statusPublisher
            .receive(on: DispatchQueue.main)
            .sink { [weak self] s in self?.status = s }
            .store(in: &cancellables)

        player.timePublisher
            .receive(on: DispatchQueue.main)
            .sink { [weak self] t in
                self?.currentTime = t.seconds
            }
            .store(in: &cancellables)
    }

    // MARK: - Actions (forwarded to Player)

    public func play()  { player?.play() }
    public func pause() { player?.pause() }
    public func stop()  { player?.stop() }

    public func seek(to seconds: Double) {
        Task { await player?.seek(to: CMTime(seconds: seconds, preferredTimescale: 600)) }
    }

    public func skip(by seconds: Double) {
        Task { await player?.skip(by: seconds) }
    }

    public func togglePlayPause() {
        if isPlaying { pause() } else { play() }
    }

    public func setVolume(_ v: Float) {
        volume = v
        player?.volume = v
    }

    public func toggleMute() {
        isMuted.toggle()
        player?.isMuted = isMuted
    }

    // MARK: - Format Helpers

    public func formattedTime(_ seconds: Double) -> String {
        let s = Int(max(0, seconds))
        let h = s / 3600
        let m = (s % 3600) / 60
        let sec = s % 60
        if h > 0 {
            return String(format: "%d:%02d:%02d", h, m, sec)
        }
        return String(format: "%02d:%02d", m, sec)
    }
}
