// HiVideoPlayer.swift — PlaybackKit
// AVPlayer + ffmpeg remux 播放器
// MKV/AVI 等不支持的容器先用 ffmpeg remux 成临时 MP4，再用 AVPlayer 播放
// 转码仅换容器（-c copy），速度极快，不损失画质

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

    public let avPlayer = AVPlayer()

    private var timeObserver: Any?
    private var statusObserver: NSKeyValueObservation?
    private var itemEndObserver: NSObjectProtocol?
    private var currentItem: AVPlayerItem?
    private var tempFileURL: URL?   // remux 临时文件

    // AVPlayer 不支持的容器 → 需要 remux
    private static let remuxRequired: Set<String> = [
        "mkv", "avi", "ts", "m2ts", "mts", "rmvb", "rm",
        "wmv", "flv", "webm", "3gp", "divx",
    ]

    // MARK: - Init

    public init() {
        avPlayer.automaticallyWaitsToMinimizeStalling = true
        setupTimeObserver()
    }

    deinit {
        if let obs = timeObserver { avPlayer.removeTimeObserver(obs) }
        itemEndObserver.map { NotificationCenter.default.removeObserver($0) }
        cleanupTempFile()
    }

    // MARK: - Load

    public func load(_ url: URL) async {
        print("[Player] load: \(url.lastPathComponent)")
        status = .loading

        avPlayer.pause()
        statusObserver?.invalidate()
        itemEndObserver.map { NotificationCenter.default.removeObserver($0) }
        cleanupTempFile()

        // 判断是否需要 remux
        let ext = url.pathExtension.lowercased()
        let playURL: URL
        if Self.remuxRequired.contains(ext) {
            print("[Player] Remuxing \(ext) → mp4...")
            if let remuxed = await remuxToMP4(url: url) {
                playURL = remuxed
                tempFileURL = remuxed
                print("[Player] Remux done → \(remuxed.lastPathComponent)")
            } else {
                print("[Player] Remux failed — trying direct playback anyway")
                playURL = url
            }
        } else {
            playURL = url
        }

        // 创建 AVPlayerItem
        let item = AVPlayerItem(url: playURL)
        currentItem = item
        avPlayer.replaceCurrentItem(with: item)

        // 播放结束通知
        itemEndObserver = NotificationCenter.default.addObserver(
            forName: .AVPlayerItemDidPlayToEndTime,
            object: item, queue: .main
        ) { [weak self] _ in
            Task { @MainActor [weak self] in self?.status = .ended }
        }

        // 等待就绪
        await waitForReady(item: item)
        print("[Player] load end: \(status)")
    }

    private func waitForReady(item: AVPlayerItem) async {
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
                    switch item.status {
                    case .readyToPlay:
                        self.duration  = item.duration
                        self.videoSize = self.extractVideoSize(from: item)
                        self.status    = .ready
                        print("[Player] ✓ ready  dur=\(String(format:"%.1f",item.duration.seconds))s")
                        finish()
                    case .failed:
                        let msg = item.error?.localizedDescription ?? "Unknown"
                        print("[Player] ✗ failed: \(msg)")
                        self.status = .error(msg)
                        finish()
                    default: break
                    }
                }
            }

            Task {
                try? await Task.sleep(nanoseconds: 30_000_000_000) // 30s timeout (remux can take time)
                print("[Player] ⚠ timeout status=\(item.status.rawValue)")
                finish()
            }
        }
    }

    // MARK: - Playback Control

    public func play() {
        guard status == .ready || status == .paused else {
            print("[Player] play() ignored – status=\(status)")
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
        cleanupTempFile()
    }

    public func seek(to time: CMTime) async {
        await avPlayer.seek(to: time, toleranceBefore: .zero, toleranceAfter: .zero)
    }

    // MARK: - Remux (MKV → MP4, copy streams, no re-encode)

    private func remuxToMP4(url: URL) async -> URL? {
        guard let ffmpeg = findFFmpeg() else {
            print("[Player] ffmpeg not found — install: brew install ffmpeg")
            return nil
        }

        // 临时文件放在系统临时目录
        let tmpDir = FileManager.default.temporaryDirectory
        let tmpFile = tmpDir.appendingPathComponent("hivideo_\(url.deletingPathExtension().lastPathComponent).mp4")

        // 如果缓存存在且大小 > 0 直接复用
        if let size = try? tmpFile.resourceValues(forKeys: [.fileSizeKey]).fileSize, size > 0 {
            print("[Player] Using cached remux: \(tmpFile.lastPathComponent)")
            return tmpFile
        }

        return await withCheckedContinuation { cont in
            Task.detached(priority: .userInitiated) {
                let proc = Process()
                proc.executableURL = URL(fileURLWithPath: ffmpeg)
                proc.arguments = [
                    "-i",  url.path,
                    "-c",  "copy",          // 仅换容器，不转码
                    "-movflags", "faststart", // MP4 优化：moov 移到文件头
                    "-y",
                    tmpFile.path,
                ]
                let errPipe = Pipe()
                proc.standardOutput = FileHandle.nullDevice
                proc.standardError  = errPipe

                do {
                    try proc.run()
                    proc.waitUntilExit()
                    let errOut = String(data: errPipe.fileHandleForReading.readDataToEndOfFile(),
                                        encoding: .utf8) ?? ""
                    let ok = proc.terminationStatus == 0 &&
                             FileManager.default.fileExists(atPath: tmpFile.path)
                    print("[Player] remux exit=\(proc.terminationStatus) ok=\(ok)")
                    if !ok { print("[Player] remux stderr: \(errOut.suffix(500))") }
                    cont.resume(returning: ok ? tmpFile : nil)
                } catch {
                    print("[Player] remux process error: \(error)")
                    cont.resume(returning: nil)
                }
            }
        }
    }

    // MARK: - Helpers

    private func cleanupTempFile() {
        if let tmp = tempFileURL {
            try? FileManager.default.removeItem(at: tmp)
            tempFileURL = nil
        }
    }

    private func findFFmpeg() -> String? {
        ["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/usr/bin/ffmpeg"]
            .first { FileManager.default.isExecutableFile(atPath: $0) }
    }

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
