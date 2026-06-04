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

    public func load(_ url: URL) async throws {
        status = .loading

        let asset = AVAsset(url: url)
        self.asset = asset

        // 加载基本属性
        let (tracks, _) = try await asset.load(.tracks, .duration)
        let dur = try await asset.load(.duration)
        duration = dur

        // 视频轨道信息
        if let vTrack = tracks.first(where: { $0.mediaType == .video }) {
            let size = try await vTrack.load(.naturalSize)
            videoSize = size
            await detectHDR(from: vTrack)
        }

        // 音频/字幕轨道枚举
        await loadTrackInfo(from: asset)

        status = .ready
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

            // 视频输出（VideoToolbox 解码后 CVPixelBuffer）
            if let vTrack = try? await asset.loadTracks(withMediaType: .video).first {
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
        var audio: [TrackInfo] = []
        var subs: [TrackInfo] = []

        if let audioTracks = try? await asset.loadTracks(withMediaType: .audio) {
            for (idx, track) in audioTracks.enumerated() {
                let lang = (try? await track.load(.languageCode)) ?? "und"
                audio.append(TrackInfo(
                    id: idx,
                    language: lang,
                    title: "音频 \(idx + 1)",
                    codec: "AAC",
                    isDefault: idx == 0
                ))
            }
        }

        if let subTracks = try? await asset.loadTracks(withMediaType: .text) {
            for (idx, track) in subTracks.enumerated() {
                let lang = (try? await track.load(.languageCode)) ?? "und"
                subs.append(TrackInfo(
                    id: idx,
                    language: lang,
                    title: "字幕 \(idx + 1)",
                    codec: "SRT"
                ))
            }
        }

        audioTracks = audio
        subtitleTracks = subs
    }

    private func detectHDR(from track: AVAssetTrack) async {
        // 通过 formatDescriptions 检测 HDR 格式
        guard let descs = try? await track.load(.formatDescriptions),
              let desc = descs.first else { return }

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
