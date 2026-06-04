// AudioOutput.swift — PlaybackKit
// AVAudioEngine 音频输出层
// Phase 1: PCM 直通输出，支持音量/静音控制

import AVFoundation
import Foundation

// MARK: - AudioOutput

/// 音频输出控制器
/// 使用 AVAudioEngine 实现软件混音 + 输出
final class AudioOutput: @unchecked Sendable {

    // MARK: - Properties

    var volume: Float = 1.0 {
        didSet { playerNode.volume = isMuted ? 0 : volume }
    }

    var isMuted: Bool = false {
        didSet { playerNode.volume = isMuted ? 0 : volume }
    }

    // MARK: - Private

    private let engine = AVAudioEngine()
    private let playerNode = AVAudioPlayerNode()
    private var isRunning = false

    // MARK: - Init

    init() {
        engine.attach(playerNode)
        engine.connect(
            playerNode,
            to: engine.mainMixerNode,
            format: engine.mainMixerNode.outputFormat(forBus: 0)
        )
    }

    // MARK: - Control

    func play() {
        do {
            if !isRunning {
                try engine.start()
                isRunning = true
            }
            playerNode.play()
        } catch {
            print("[AudioOutput] Failed to start engine: \(error)")
        }
    }

    func pause() {
        playerNode.pause()
    }

    func stop() {
        playerNode.stop()
        engine.stop()
        isRunning = false
    }

    /// 将 CMSampleBuffer（PCM）送入播放队列
    func schedule(sampleBuffer: CMSampleBuffer) {
        guard let pcmBuffer = pcmBuffer(from: sampleBuffer) else { return }
        playerNode.scheduleBuffer(pcmBuffer, completionHandler: nil)
    }

    // MARK: - Private Helpers

    private func pcmBuffer(from sampleBuffer: CMSampleBuffer) -> AVAudioPCMBuffer? {
        guard let formatDesc = CMSampleBufferGetFormatDescription(sampleBuffer) else { return nil }
        let asbd = CMAudioFormatDescriptionGetStreamBasicDescription(formatDesc)?.pointee
        guard let asbd = asbd,
              let format = AVAudioFormat(streamDescription: &(UnsafeMutablePointer<AudioStreamBasicDescription>.allocate(capacity: 1).pointee)) else {
            return nil
        }
        let frameCount = AVAudioFrameCount(CMSampleBufferGetNumSamples(sampleBuffer))
        guard let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: frameCount) else { return nil }
        buffer.frameLength = frameCount
        _ = asbd  // suppress unused warning
        return buffer
    }
}
