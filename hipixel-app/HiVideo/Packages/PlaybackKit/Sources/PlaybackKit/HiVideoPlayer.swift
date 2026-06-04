// HiVideoPlayer.swift — PlaybackKit
// 主播放器实现：AVFoundation 解复用 + VideoToolbox 硬解 + Metal 渲染
//
// 技术路径：
//   AVAsset/AVAssetReader  → 解复用（视频/音频轨道分离）
//   VideoToolbox           → H.264/H.265 硬件解码 → CVPixelBuffer
//   Metal / CAMetalLayer   → GPU 渲染（MetalRenderer）
//   AVAudioEngine          → PCM 音频输出
//
// 说明：Phase 1 使用 AVFoundation 做解复用（无需额外 FFmpeg 依赖），
//       VideoToolbox 做硬解，Metal 做渲染。
//       Phase 2.5 Rust 迁移时可替换解复用层，Player 协议不变。

import Foundation
import AVFoundation
import VideoToolbox
import CoreMedia
import CoreVideo
import Combine

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
        didSet { audioOutput.volume = volume }
    }
    public var isMuted: Bool = false {
        didSet { audioOutput.isMuted = isMuted }
    }
    public var rate: Float = 1.0 {
        didSet { displayLink?.rate = Double(rate) }
    }
    public var selectedAudioTrack: Int = 0
    public var selectedSubtitleTrack: Int? = nil

    public var statusPublisher: AnyPublisher<PlaybackStatus, Never> {
        $status.eraseToAnyPublisher()
    }
    public var timePublisher: AnyPublisher<CMTime, Never> {
        $currentTime.eraseToAnyPublisher()
    }

    // MARK: - Private State

    private var asset: AVAsset?
    private var assetReader: AVAssetReader?
    private var videoOutput: AVAssetReaderTrackOutput?
    private var audioOutput: AudioOutput = AudioOutput()
    private var displayLink: DisplayLink?
    private var currentURL: URL?

    /// Metal 渲染器（由外部通过 makeRenderer() 获取后注入到 MTKView）
    public let renderer: MetalRenderer = MetalRenderer()

    // 时间控制
    private var startTime: CFAbsoluteTime = 0
    private var seekTime: Double = 0
    private var isSeekPending: Bool = false
    private var seekContinuation: CheckedContinuation<Void, Never>?

    // MARK: - Init / Deinit

    public init() {
        self.audioOutput = AudioOutput()
    }

    deinit {
        displayLink?.stop()
    }

    // MARK: - Load

    // 容器格式：AVFoundation 不支持的，标记为 ffmpegRequired
    private static let avUnsupported: Set<String> = [
        "mkv", "avi", "ts", "m2ts", "mts", "rmvb", "rm", "wmv", "flv", "webm",
    ]

    public func load(_ url: URL) async {
        status = .loading
        currentURL = url

        let ext = url.pathExtension.lowercased()
        let needsFFmpeg = Self.avUnsupported.contains(ext)

        if needsFFmpeg {
            // MKV 等：用 ffprobe 获取基本信息，播放走 ffmpeg pipe（Phase 2.5 实现）
            // Phase 1 先标记 ready 并记录 URL，播放时走 AVPlayer 尝试（部分 MKV 可播）
            await loadWithAVPlayer(url: url)
        } else {
            await loadWithAVAssetReader(url: url)
        }
    }

    private func loadWithAVAssetReader(url: URL) async {
        let asset = AVURLAsset(url: url,
                               options: [AVURLAssetPreferPreciseDurationAndTimingKey: false])

        // 用 loadValuesAsynchronously 避免 async/await 路径触发内部校验日志
        let loaded: Bool = await withCheckedContinuation { cont in
            asset.loadValuesAsynchronously(forKeys: ["tracks", "duration", "playable"]) {
                let s = asset.statusOfValue(forKey: "duration", error: nil)
                cont.resume(returning: s == .loaded)
            }
        }

        guard loaded else {
            status = .error("无法加载文件")
            return
        }

        self.asset = asset
        duration = asset.duration

        if let vTrack = asset.tracks(withMediaType: .video).first {
            let size = vTrack.naturalSize.applying(vTrack.preferredTransform)
            videoSize = CGSize(width: abs(size.width), height: abs(size.height))
            await detectHDR(from: vTrack)
        }

        await loadTrackInfo(from: asset)
        status = .ready
    }

    private func loadWithAVPlayer(url: URL) async {
        // MKV Phase 1 兜底：直接用 AVPlayer（部分 MKV H.264 可播，全靠系统）
        // 不走 AVAsset 的属性加载，避免签名校验日志
        // 仅设置基本状态，实际 duration/videoSize 会在 pipeline 启动后更新
        self.asset = AVAsset(url: url)
        // 用 ffprobe 静默获取 duration
        let dur = await ffprobeDuration(url: url)
        if dur > 0 {
            duration = CMTime(seconds: dur, preferredTimescale: 600)
        }
        status = .ready
    }

    private func ffprobeDuration(url: URL) async -> Double {
        return await withCheckedContinuation { cont in
            Task.detached(priority: .utility) {
                let candidates = ["/opt/homebrew/bin/ffprobe",
                                  "/usr/local/bin/ffprobe", "/usr/bin/ffprobe"]
                guard let ffprobe = candidates.first(where: {
                    FileManager.default.isExecutableFile(atPath: $0)
                }) else {
                    cont.resume(returning: 0)
                    return
                }
                let proc = Process()
                proc.executableURL = URL(fileURLWithPath: ffprobe)
                proc.arguments = ["-v", "quiet",
                                   "-show_entries", "format=duration",
                                   "-of", "default=noprint_wrappers=1:nokey=1",
                                   url.path]
                let pipe = Pipe()
                proc.standardOutput = pipe
                proc.standardError  = FileHandle.nullDevice
                try? proc.run()
                proc.waitUntilExit()
                let out = String(data: pipe.fileHandleForReading.readDataToEndOfFile(),
                                 encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
                cont.resume(returning: Double(out) ?? 0)
            }
        }
    }

    // MARK: - Playback Control

    public func play() {
        guard status == .ready || status == .paused else { return }
        status = .playing
        startPlaybackPipeline()
    }

    public func pause() {
        guard status == .playing else { return }
        status = .paused
        displayLink?.stop()
        audioOutput.pause()
    }

    public func stop() {
        displayLink?.stop()
        audioOutput.stop()
        assetReader?.cancelReading()
        assetReader = nil
        currentTime = .zero
        status = .idle
    }

    public func seek(to time: CMTime) async {
        seekTime = time.seconds
        isSeekPending = true
        // 重建 pipeline 从新位置读取
        if status == .playing || status == .paused {
            displayLink?.stop()
            assetReader?.cancelReading()
            assetReader = nil
            await rebuildPipeline(from: time)
            if status == .playing {
                startDisplayLink()
            }
        }
    }

    // MARK: - Private: Pipeline

    private func startPlaybackPipeline() {
        let startCMTime = CMTime(seconds: seekTime, preferredTimescale: 600)
        Task {
            await rebuildPipeline(from: startCMTime)
            startDisplayLink()
            audioOutput.play()
        }
    }

    private func rebuildPipeline(from time: CMTime) async {
        guard let asset = asset else { return }
        do {
            let reader = try AVAssetReader(asset: asset)
            let timeRange = CMTimeRange(start: time, end: asset.duration)
            reader.timeRange = timeRange

            // 视频输出：用同步 tracks(withMediaType:) 避免 async 触发签名校验
            if let vTrack = asset.tracks(withMediaType: .video).first {
                let settings: [String: Any] = [
                    kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA,
                ]
                let output = AVAssetReaderTrackOutput(track: vTrack, outputSettings: settings)
                output.alwaysCopiesSampleData = false
                if reader.canAdd(output) {
                    reader.add(output)
                    videoOutput = output
                }
            }

            reader.startReading()
            assetReader = reader
        } catch {
            status = .error(error.localizedDescription)
        }
    }

    private func startDisplayLink() {
        displayLink = DisplayLink(fps: 60) { [weak self] in
            self?.renderNextFrameFromDisplayLink()
        }
        displayLink?.rate = Double(rate)
        displayLink?.start()
    }

    /// CVDisplayLink 回调线程上调用（非 MainActor）
    private nonisolated func renderNextFrameFromDisplayLink() {
        Task { await renderNextFrame() }
    }

    private func renderNextFrame() {
        guard let output = videoOutput,
              let sampleBuffer = output.copyNextSampleBuffer() else {
            // 读取结束
            if assetReader?.status == .completed {
                Task { @MainActor in
                    self.status = .ended
                    self.displayLink?.stop()
                }
            }
            return
        }

        let pts = CMSampleBufferGetPresentationTimeStamp(sampleBuffer)
        Task { @MainActor in
            self.currentTime = pts
        }

        // 取 CVPixelBuffer 送 Metal 渲染
        if let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) {
            renderer.enqueue(pixelBuffer: pixelBuffer, pts: pts)
        }
    }

    // MARK: - Private: Track Info

    private func loadTrackInfo(from asset: AVAsset) async {
        // 用同步 tracks(withMediaType:) 避免 async load 触发 AVFoundation 校验日志
        let audioTrackList = asset.tracks(withMediaType: .audio)
        let subTrackList   = asset.tracks(withMediaType: .text)

        audioTracks = audioTrackList.enumerated().map { idx, track in
            let lang = track.languageCode ?? "und"
            return TrackInfo(id: idx, language: lang,
                             title: "音频 \(idx + 1)", codec: "AAC", isDefault: idx == 0)
        }
        subtitleTracks = subTrackList.enumerated().map { idx, track in
            let lang = track.languageCode ?? "und"
            return TrackInfo(id: idx, language: lang,
                             title: "字幕 \(idx + 1)", codec: "SRT")
        }
    }

    private func detectHDR(from track: AVAssetTrack) async {
        guard let rawDesc = track.formatDescriptions.first else { return }
        let desc = rawDesc as! CMFormatDescription

        let extensions = CMFormatDescriptionGetExtensions(desc) as? [String: Any] ?? [:]
        let transferFunction = extensions[kCMFormatDescriptionExtension_TransferFunction as String] as? String ?? ""

        if transferFunction.contains("ITU_R_2100") || transferFunction.contains("ST_2084") {
            hdrMetadata = HDRMetadata(format: .hdr10)
        } else if transferFunction.contains("HLG") {
            hdrMetadata = HDRMetadata(format: .hlg)
        }
    }
}

// MARK: - DisplayLink Helper

/// 基于 CVDisplayLink 的帧计时器（macOS）
final class DisplayLink: @unchecked Sendable {
    private var displayLink: CVDisplayLink?
    private let callback: @Sendable () -> Void
    var rate: Double = 1.0

    init(fps: Int = 60, callback: @escaping @Sendable () -> Void) {
        self.callback = callback
        CVDisplayLinkCreateWithActiveCGDisplays(&displayLink)
        guard let dl = displayLink else { return }
        let cb: CVDisplayLinkOutputCallback = { _, _, _, _, _, userInfo in
            let self_ = Unmanaged<DisplayLink>.fromOpaque(userInfo!).takeUnretainedValue()
            self_.callback()
            return kCVReturnSuccess
        }
        CVDisplayLinkSetOutputCallback(dl, cb, Unmanaged.passUnretained(self).toOpaque())
    }

    func start() {
        guard let dl = displayLink else { return }
        CVDisplayLinkStart(dl)
    }

    func stop() {
        guard let dl = displayLink else { return }
        CVDisplayLinkStop(dl)
    }

    deinit { stop() }
}
