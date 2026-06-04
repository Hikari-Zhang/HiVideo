// HiVideoPlayer.swift — PlaybackKit
// AVPlayer + AVPlayerLayer 播放器

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

    // MARK: - AVPlayer (public for AVPlayerLayerView)

    public let avPlayer = AVPlayer()

    private var timeObserver: Any?
    private var statusObserver: NSKeyValueObservation?
    private var rateObserver: NSKeyValueObservation?
    private var itemEndObserver: NSObjectProtocol?
    private var currentItem: AVPlayerItem?

    // MARK: - Init

    public init() {
        avPlayer.automaticallyWaitsToMinimizeStalling = true
        setupTimeObserver()
    }

    deinit {
        if let obs = timeObserver { avPlayer.removeTimeObserver(obs) }
        itemEndObserver.map { NotificationCenter.default.removeObserver($0) }
    }

    // MARK: - Load

    public func load(_ url: URL) async {
        print("[Player] load start: \(url.lastPathComponent)")
        status = .loading

        avPlayer.pause()
        statusObserver?.invalidate()
        rateObserver?.invalidate()
        itemEndObserver.map { NotificationCenter.default.removeObserver($0) }

        let item = AVPlayerItem(url: url)   // 用 URL 直接初始化（更简单，系统自动选解码器）
        currentItem = item
        avPlayer.replaceCurrentItem(with: item)
        print("[Player] replaceCurrentItem done, item.status=\(item.status.rawValue)")

        // 观察播放完毕
        itemEndObserver = NotificationCenter.default.addObserver(
            forName: .AVPlayerItemDidPlayToEndTime,
            object: item, queue: .main
        ) { [weak self] _ in
            Task { @MainActor [weak self] in self?.status = .ended }
        }

        // 等待 readyToPlay（用 initial option 捕获已经就绪的状态）
        await withCheckedContinuation { (cont: CheckedContinuation<Void, Never>) in
            var done = false

            let finish = { @Sendable in
                guard !done else { return }
                done = true
                cont.resume()
            }

            statusObserver = item.observe(\.status, options: [.initial, .new]) { [weak self] item, _ in
                guard let self else { return }
                Task { @MainActor in
                    print("[Player] KVO status=\(item.status.rawValue) error=\(String(describing: item.error))")
                    switch item.status {
                    case .readyToPlay:
                        self.duration  = item.duration
                        self.videoSize = self.extractVideoSize(from: item)
                        self.status    = .ready
                        print("[Player] ✓ ready  dur=\(item.duration.seconds)s  size=\(self.videoSize)")
                        finish()
                    case .failed:
                        let msg = item.error?.localizedDescription ?? "unknown"
                        print("[Player] ✗ failed: \(msg)")
                        self.status = .error(msg)
                        finish()
                    default:
                        break
                    }
                }
            }

            // 15 秒超时
            Task {
                try? await Task.sleep(nanoseconds: 15_000_000_000)
                print("[Player] ⚠ timeout  status=\(item.status.rawValue)")
                finish()
            }
        }
        print("[Player] load end: status=\(status)")
    }

    // MARK: - Playback Control

    public func play() {
        print("[Player] play()  status=\(status)  item=\(String(describing: avPlayer.currentItem?.status.rawValue))")
        guard status == .ready || status == .paused else {
            print("[Player] play() ignored – not ready/paused")
            return
        }
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
        guard let track = item.asset.tracks(withMediaType: .video).first else { return .zero }
        let size = track.naturalSize.applying(track.preferredTransform)
        return CGSize(width: abs(size.width), height: abs(size.height))
    }
}
