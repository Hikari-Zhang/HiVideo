// PlayerWindowView.swift — HiVideo
// 沉浸式播放器窗口：AVPlayerLayer + 控制条 + 快捷键

import SwiftUI
import AVKit
import PlaybackKit

struct PlayerWindowView: View {
    @EnvironmentObject var player: HiVideoPlayer
    @EnvironmentObject var playerState: PlayerStateObject

    @State private var controlsVisible = true
    @State private var hideTimer: Timer?

    var body: some View {
        ZStack(alignment: .bottom) {
            // ── 视频画面（AVPlayerLayer）──
            Color.black.ignoresSafeArea()
            AVPlayerLayerView(player: player.avPlayer)
                .ignoresSafeArea()

            // ── HDR 标识 ──
            if let hdr = player.hdrMetadata {
                HDRBadge(format: hdr.format)
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topTrailing)
                    .padding(.top, 16).padding(.trailing, 16)
                    .opacity(controlsVisible ? 0 : 1)
                    .animation(.easeInOut(duration: 0.3), value: controlsVisible)
            }

            // ── 控制条 ──
            if controlsVisible {
                PlayerControlBar(playerState: playerState)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
            }
        }
        .frame(minWidth: 640, minHeight: 360)
        .background(Color.black)
        .onContinuousHover { phase in
            switch phase {
            case .active: showControls()
            case .ended:  scheduleHide()
            }
        }
        // 快捷键
        .onKeyPress(.space)     { playerState.togglePlayPause(); return .handled }
        .onKeyPress(.leftArrow) { playerState.skip(by: -5);      return .handled }
        .onKeyPress(.rightArrow){ playerState.skip(by:  5);      return .handled }
        .onKeyPress(.upArrow)   { playerState.setVolume(min(1, playerState.volume + 0.1)); return .handled }
        .onKeyPress(.downArrow) { playerState.setVolume(max(0, playerState.volume - 0.1)); return .handled }
        .onKeyPress(characters: CharacterSet(charactersIn: "mM"), phases: .down) { _ in
            playerState.toggleMute(); return .handled
        }
        .onKeyPress(characters: CharacterSet(charactersIn: "fF"), phases: .down) { _ in
            toggleFullscreen(); return .handled
        }
        .onAppear {
            playerState.bind(to: player)
        }
    }

    // MARK: - Controls Visibility

    private func showControls() {
        hideTimer?.invalidate()
        withAnimation(.spring(response: 0.2, dampingFraction: 0.85)) {
            controlsVisible = true
        }
        scheduleHide()
    }

    private func scheduleHide() {
        hideTimer?.invalidate()
        guard playerState.isPlaying else { return }
        hideTimer = Timer.scheduledTimer(withTimeInterval: 2.5, repeats: false) { _ in
            Task { @MainActor in
                withAnimation(.easeInOut(duration: 0.3)) {
                    self.controlsVisible = false
                }
            }
        }
    }

    private func toggleFullscreen() {
        NSApp.keyWindow?.toggleFullScreen(nil)
        playerState.isFullscreen.toggle()
    }
}

// MARK: - AVPlayerLayer View (NSViewRepresentable)

struct AVPlayerLayerView: NSViewRepresentable {
    let player: AVPlayer

    func makeCoordinator() -> Coordinator {
        Coordinator(player: player)
    }

    func makeNSView(context: Context) -> NSView {
        let view = NSView()
        // 先设 layer，再设 wantsLayer=true
        // NSView 会把 layer 作为自己的 backing layer（而非 sublayer）
        view.layer = context.coordinator.playerLayer
        view.wantsLayer = true
        return view
    }

    func updateNSView(_ nsView: NSView, context: Context) {
        // player 引用不变，layer 已绑定，无需操作
    }

    final class Coordinator: NSObject {
        let playerLayer: AVPlayerLayer
        init(player: AVPlayer) {
            playerLayer = AVPlayerLayer(player: player)
            playerLayer.videoGravity = .resizeAspect
            playerLayer.backgroundColor = CGColor.black
        }
    }
}

// MARK: - Player Control Bar

struct PlayerControlBar: View {
    @ObservedObject var playerState: PlayerStateObject
    @State private var isDraggingProgress = false
    @State private var dragProgress: Double = 0

    var body: some View {
        VStack(spacing: 0) {
            // 进度条
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    Capsule().fill(Color.white.opacity(0.2))
                    Capsule()
                        .fill(Color.accentColor)
                        .frame(width: geo.size.width * (isDraggingProgress ? dragProgress : playerState.progress))
                }
                .frame(height: isDraggingProgress ? 8 : 4)
                .animation(.spring(response: 0.15, dampingFraction: 0.9), value: isDraggingProgress)
                .contentShape(Rectangle())
                .gesture(
                    DragGesture(minimumDistance: 0)
                        .onChanged { v in
                            isDraggingProgress = true
                            dragProgress = max(0, min(1, v.location.x / geo.size.width))
                        }
                        .onEnded { _ in
                            playerState.seek(to: dragProgress * playerState.duration)
                            isDraggingProgress = false
                        }
                )
            }
            .frame(height: 8)
            .padding(.horizontal, 12)
            .padding(.top, 12)

            // 按钮行
            HStack(spacing: 16) {
                HStack(spacing: 10) {
                    ctrlBtn("backward.end.fill", size: 16) {}
                    ctrlBtn("gobackward.5", size: 18)    { playerState.skip(by: -5) }
                    Button { playerState.togglePlayPause() } label: {
                        Image(systemName: playerState.isPlaying ? "pause.fill" : "play.fill")
                            .font(.system(size: 22, weight: .medium))
                            .foregroundColor(.white)
                            .frame(width: 32, height: 32)
                    }
                    .buttonStyle(.plain)
                    ctrlBtn("goforward.5", size: 18)     { playerState.skip(by:  5) }
                    ctrlBtn("forward.end.fill", size: 16) {}
                }

                HStack(spacing: 4) {
                    Text(playerState.formattedTime(playerState.currentTime))
                        .font(.system(size: 13, weight: .medium, design: .monospaced))
                        .foregroundColor(.white)
                    Text("/")
                        .font(.system(size: 12, design: .monospaced))
                        .foregroundColor(.white.opacity(0.5))
                    Text(playerState.formattedTime(playerState.duration))
                        .font(.system(size: 13, weight: .medium, design: .monospaced))
                        .foregroundColor(.white.opacity(0.7))
                }

                Spacer()

                HStack(spacing: 8) {
                    ctrlBtn(volumeIcon, size: 17) { playerState.toggleMute() }
                    Slider(value: Binding(
                        get: { Double(playerState.volume) },
                        set: { playerState.setVolume(Float($0)) }
                    ), in: 0...1)
                    .frame(width: 72)
                    .controlSize(.mini)

                    ctrlBtn("captions.bubble", size: 17) {}
                    ctrlBtn("pip.enter", size: 17) {}
                    ctrlBtn("sparkles", size: 17,
                            tint: playerState.isEnhancementEnabled ? .yellow : .white) {
                        playerState.isEnhancementEnabled.toggle()
                    }
                    ctrlBtn(playerState.isFullscreen
                            ? "arrow.down.right.and.arrow.up.left"
                            : "arrow.up.left.and.arrow.down.right",
                            size: 17) {
                        NSApp.keyWindow?.toggleFullScreen(nil)
                        playerState.isFullscreen.toggle()
                    }
                }
            }
            .padding(.horizontal, 12)
            .padding(.top, 8)
            .padding(.bottom, 18)
        }
        .background(
            ZStack {
                VisualEffectBlur(material: .hudWindow, blendingMode: .withinWindow)
                LinearGradient(colors: [.black.opacity(0.4), .clear],
                               startPoint: .bottom, endPoint: .top)
            }
        )
    }

    private func ctrlBtn(_ symbol: String, size: CGFloat,
                         tint: Color = .white, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: symbol)
                .font(.system(size: size))
                .foregroundColor(tint)
                .frame(width: 28, height: 28)
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }

    private var volumeIcon: String {
        if playerState.isMuted || playerState.volume == 0 { return "speaker.slash.fill" }
        if playerState.volume < 0.4 { return "speaker.wave.1.fill" }
        if playerState.volume < 0.7 { return "speaker.wave.2.fill" }
        return "speaker.wave.3.fill"
    }
}

// MARK: - HDR Badge

struct HDRBadge: View {
    let format: HDRMetadata.HDRFormat
    var body: some View {
        Text(format.rawValue)
            .font(.system(size: 10, weight: .bold))
            .foregroundColor(.yellow)
            .padding(.horizontal, 7)
            .padding(.vertical, 3)
            .background(Color.yellow.opacity(0.15))
            .overlay(Capsule().stroke(Color.yellow.opacity(0.5), lineWidth: 0.5))
            .clipShape(Capsule())
    }
}

// MARK: - Visual Effect Blur

struct VisualEffectBlur: NSViewRepresentable {
    let material: NSVisualEffectView.Material
    let blendingMode: NSVisualEffectView.BlendingMode
    func makeNSView(context: Context) -> NSVisualEffectView {
        let v = NSVisualEffectView()
        v.material = material; v.blendingMode = blendingMode; v.state = .active
        return v
    }
    func updateNSView(_ nsView: NSVisualEffectView, context: Context) {}
}
