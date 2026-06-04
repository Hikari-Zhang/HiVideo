// HiVideoPlayer.swift — PlaybackKit
// 播放器实现：AVPlayer + AVPlayerLayer（系统级硬解，支持 MKV H.264/H.265）
//
// Phase 1 策略：
//   使用 AVPlayer + AVPlayerLayer 渲染，系统处理所有格式的解码和渲染
//   包括 MKV（通过系统 codec 支持）、MP4、MOV 等
//   Phase 2.5 Rust 迁移时替换为 Metal 渲染管道，Player 协议不变

import AVFoundation
import Combine
import CoreMedia
import Foundation

@MainActor
public final class HiVideoPlayer: Player, ObservableObject {

    // MARK: - Player Protocol

    @Published public private(set) var status: PlaybackStatus = .idle
    @Published public private(set) var currentTime: CMTime = .zero
    @Published public private(set) var duration: CMTime = .zero
    @Published public private(set) var videoSize: CGSize = .zero
    @Published public private(set) var hdrMetadata: HDRMetadata? = nil
    @Published public private(set) var audioTracks: [TrackInfo] = []
    @Published public private(set) var subtitleTracks: [TrackInfo] = []

    public var volume: Float = 1.0 {
        didSet { avPlayer.volume = isMuted ? 0 : volume }
    }
    public var isMuted: Bool = false {
        didSet { avPlayer.isMuted = isMuted }
    }
    public var rate: Float = 1.0 {
        didSet { if status == .playing { avPlayer.rate = rate } }
    }
    public var selectedAudioTrack: Int = 0
    public var selectedSubtitleTrack: Int? = nil

    public var statusPublisher: AnyPublisher<PlaybackStatus, Never> {
        $status.eraseToAnyPublisher()
    }
    public var timePublisher: AnyPublisher<CMTime, Never> {
        $currentTime.eraseToAnyPublisher()
    }

    // MARK: - AVPlayer

    /// 外部通过此属性获取 AVPlayerLayer（供 PlayerVideoView 使用）
    public let avPlayer = AVPlayer()

    private var timeObserver: Any?
    private var statusObserver: NSKeyValueObservation?
    private var itemEndObserver: NSObjectProtocol?
    private var currentItem: AVPlayerItem?

    // MARK: - Init

    public init() {
        avPlayer.automaticallyWaitsToMinimizeStalling = true
        setupTimeObserver()
    }

    deinit {
        if let obs = timeObserver {
            avPlayer.removeTimeObserver(obs)
        }
        itemEndObserver.map { NotificationCenter.default.removeObserver($0) }
    }

    // MARK: - Load

    public func load(_ url: URL) async {
        status = .loading

        // 停止当前播放
        avPlayer.pause()
        statusObserver?.invalidate()
        itemEndObserver.map { NotificationCenter.default.removeObserver($0) }

        let asset = AVURLAsset(url: url)
        let item = AVPlayerItem(asset: asset)
        currentItem = item
        avPlayer.replaceCurrentItem(with: item)

        // 观察 playerItem status
        statusObserver = item.observe(\.status, options: [.new]) { [weak self] item, _ in
            Task { @MainActor [weak self] in
                guard let self else { return }
                switch item.status {
                case .readyToPlay:
                    self.duration = item.duration
                    self.videoSize = self.extractVideoSize(from: item)
                    self.status = .ready
                case .failed:
                    let msg = item.error?.localizedDescription ?? "未知错误"
                    self.status = .error(msg)
                default:
                    break
                }
            }
        }

        // 播放结束通知
        itemEndObserver = NotificationCenter.default.addObserver(
            forName: .AVPlayerItemDidPlayToEndTime,
            object: item,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor [weak self] in
                self?.status = .ended
            }
        }

        // 等待就绪（最多 10 秒）
        await withCheckedContinuation { (cont: CheckedContinuation<Void, Never>) in
            var resolved = false
            let obs = item.observe(\.status, options: [.new]) { item, _ in
                guard !resolved else { return }
                if item.status == .readyToPlay || item.status == .failed {
                    resolved = true
                    cont.resume()
                }
            }
            // 超时保护
            Task {
                try? await Task.sleep(nanoseconds: 10_000_000_000)
                if !resolved {
                    resolved = true
                    obs.invalidate()
                    cont.resume()
                }
            }
            _ = obs // 持有引用直到 resume
        }
    }

    // MARK: - Playback Control

    public func play() {
        guard status == .ready || status == .paused else { return }
        avPlayer.rate = rate
        avPlayer.play()
        status = .playing
    }

    public func pause() {
        guard status == .playing else { return }
        avPlayer.pause()
        status = .paused
    }

    public func stop() {
        avPlayer.pause()
        avPlayer.replaceCurrentItem(with: nil)
        currentTime = .zero
        status = .idle
    }

    public func seek(to time: CMTime) async {
        await avPlayer.seek(to: time, toleranceBefore: .zero, toleranceAfter: .zero)
    }

    // MARK: - Private

    private func setupTimeObserver() {
        let interval = CMTime(seconds: 0.25, preferredTimescale: 600)
        timeObserver = avPlayer.addPeriodicTimeObserver(forInterval: interval, queue: .main) {
            [weak self] time in
            self?.currentTime = time
        }
    }

    private func extractVideoSize(from item: AVPlayerItem) -> CGSize {
        guard let track = item.asset.tracks(withMediaType: .video).first else {
            return .zero
        }
        let size = track.naturalSize.applying(track.preferredTransform)
        return CGSize(width: abs(size.width), height: abs(size.height))
    }
}
