// PlayerStateObject.swift — PlaybackKit
// 可观察的播放器状态，供 SwiftUI 视图绑定

import Foundation
import CoreMedia
import Combine
import SwiftUI

@MainActor
public final class PlayerStateObject: ObservableObject {

    @Published public var status: PlaybackStatus = .idle
    @Published public var currentTime: Double = 0
    @Published public var duration: Double = 0
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

    public var progress: Double {
        guard duration > 0 else { return 0 }
        return currentTime / duration
    }
    public var isPlaying: Bool { status == .playing }
    public var isLoaded: Bool {
        status == .ready || status == .playing ||
        status == .paused || status == .buffering
    }

    private weak var player: (any Player)?
    private var cancellables = Set<AnyCancellable>()

    public init() {}

    // MARK: - Bind

    public func bind(to player: any Player) {
        self.player = player
        cancellables.removeAll()

        player.statusPublisher
            .receive(on: DispatchQueue.main)
            .sink { [weak self] s in self?.status = s }
            .store(in: &cancellables)

        player.timePublisher
            .receive(on: DispatchQueue.main)
            .sink { [weak self] t in
                guard let self else { return }
                self.currentTime = t.seconds.isFinite ? t.seconds : 0
                // duration 在 status 变为 ready 后更新
                let d = player.duration.seconds
                if d.isFinite && d > 0 { self.duration = d }
            }
            .store(in: &cancellables)

        // 立即同步当前状态
        status   = player.status
        duration = player.duration.seconds.isFinite ? player.duration.seconds : 0
        videoSize = player.videoSize
    }

    // MARK: - Actions

    public func play()  { player?.play() }
    public func pause() { player?.pause() }
    public func stop()  { player?.stop() }

    public func seek(to seconds: Double) {
        Task { await player?.seek(to: CMTime(seconds: seconds, preferredTimescale: 600)) }
    }

    public func skip(by seconds: Double) {
        let target = max(0, min(currentTime + seconds, duration))
        seek(to: target)
    }

    public func togglePlayPause() {
        if isPlaying { pause() } else { play() }
    }

    public func setVolume(_ v: Float) {
        volume = v; player?.volume = v
    }

    public func toggleMute() {
        isMuted.toggle(); player?.isMuted = isMuted
    }

    // MARK: - Formatting

    public func formattedTime(_ seconds: Double) -> String {
        let s = Int(max(0, seconds))
        let h = s / 3600, m = (s % 3600) / 60, sec = s % 60
        if h > 0 { return String(format: "%d:%02d:%02d", h, m, sec) }
        return String(format: "%02d:%02d", m, sec)
    }
}
