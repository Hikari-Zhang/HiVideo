// PlayerControls.swift — HiVideo Core Component
// Phase 0.5 · 播放器控制条
// 对应文档：docs/design/01-hivideo-core.md §7

import SwiftUI

// MARK: - Player State

class PlayerState: ObservableObject {
    @Published var isPlaying: Bool = false
    @Published var currentTime: Double = 0       // 秒
    @Published var duration: Double = 7394       // 秒（示例：2h3m14s）
    @Published var volume: Double = 1.0
    @Published var isMuted: Bool = false
    @Published var isFullscreen: Bool = false
    @Published var isEnhancementEnabled: Bool = false
    @Published var isPictureInPicture: Bool = false
    @Published var subtitleTrack: String? = "中文"

    var progress: Double {
        guard duration > 0 else { return 0 }
        return currentTime / duration
    }

    func seek(to time: Double) {
        currentTime = max(0, min(time, duration))
    }
}

// MARK: - Player Controls Bar

struct PlayerControls: View {
    @ObservedObject var state: PlayerState
    var onTogglePlay: (() -> Void)? = nil
    var onSeek: ((Double) -> Void)? = nil
    var onToggleFullscreen: (() -> Void)? = nil
    var onToggleEnhancement: (() -> Void)? = nil

    @State private var isDraggingProgress = false
    @State private var dragProgress: Double = 0
    @State private var isHoveringProgress = false
    @State private var hoverPosition: Double = 0    // 0-1 归一化

    var body: some View {
        VStack(spacing: 0) {
            // 进度条
            progressBar

            // 控制按钮行
            controlRow
        }
        .padding(.horizontal, Spacing.md)
        .padding(.bottom, Layout.controlBarBottom)
        .frame(height: Layout.controlBarHeight)
        .background {
            #if os(macOS)
            VisualEffectView.hud
            #else
            Color.black.opacity(0.6)
            #endif
        }
    }

    // MARK: Progress Bar

    private var progressBar: some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                // 轨道背景
                Capsule()
                    .fill(Color.white.opacity(0.2))
                    .frame(height: isHoveringProgress ? 8 : 4)

                // 已播放部分
                Capsule()
                    .fill(Color.accentColor)
                    .frame(
                        width: geo.size.width * (isDraggingProgress ? dragProgress : state.progress),
                        height: isHoveringProgress ? 8 : 4
                    )
            }
            .frame(height: 8)
            .contentShape(Rectangle())
            .onHover { hovering in
                withAnimation(HiVAnimation.quick) {
                    isHoveringProgress = hovering
                }
            }
            .gesture(
                DragGesture(minimumDistance: 0)
                    .onChanged { value in
                        isDraggingProgress = true
                        dragProgress = max(0, min(1, value.location.x / geo.size.width))
                    }
                    .onEnded { value in
                        let newTime = state.duration * dragProgress
                        onSeek?(newTime)
                        state.seek(to: newTime)
                        isDraggingProgress = false
                    }
            )
        }
        .frame(height: 8)
        .padding(.horizontal, Spacing.xxs)
        .padding(.top, Spacing.sm)
    }

    // MARK: Control Row

    private var controlRow: some View {
        HStack(spacing: Spacing.lg) {
            // 左：上一个、快退、播放/暂停、快进、下一个
            leftControls

            // 时间码
            timeCode

            Spacer()

            // 右：音量、字幕、PiP、截图、画质、全屏
            rightControls
        }
        .padding(.top, Spacing.xs)
    }

    private var leftControls: some View {
        HStack(spacing: Spacing.sm) {
            controlButton("backward.end.fill", size: 16) { /* 上一个 */ }

            controlButton("gobackward.5", size: 18) {
                state.seek(to: state.currentTime - 5)
                onSeek?(state.currentTime)
            }

            // 播放/暂停（主按钮，稍大）
            Button {
                state.isPlaying.toggle()
                onTogglePlay?()
            } label: {
                Image(systemName: state.isPlaying ? "pause.fill" : "play.fill")
                    .font(.system(size: 22, weight: .medium))
                    .foregroundColor(.white)
                    .frame(width: 32, height: 32)
                    .contentShape(Circle())
            }
            .buttonStyle(.plain)
            .keyboardShortcut(.space, modifiers: [])

            controlButton("goforward.5", size: 18) {
                state.seek(to: state.currentTime + 5)
                onSeek?(state.currentTime)
            }

            controlButton("forward.end.fill", size: 16) { /* 下一个 */ }
        }
    }

    private var timeCode: some View {
        HStack(spacing: 4) {
            Text(formatTime(state.currentTime))
                .hivTimecode()
                .foregroundColor(.white)
            Text("/")
                .hivTimecode()
                .foregroundColor(.white.opacity(0.5))
            Text(formatTime(state.duration))
                .hivTimecode()
                .foregroundColor(.white.opacity(0.7))
        }
    }

    private var rightControls: some View {
        HStack(spacing: Spacing.xs) {
            // 音量
            volumeControl

            // 字幕
            controlButton(
                state.subtitleTrack != nil ? "captions.bubble.fill" : "captions.bubble",
                size: 18,
                tint: state.subtitleTrack != nil ? .accentColor : .white
            ) { /* 字幕菜单 */ }

            // 画中画
            controlButton("pip.enter", size: 18) {
                state.isPictureInPicture.toggle()
            }

            // 截图
            controlButton("camera.fill", size: 17) { /* 截图 */ }

            // 画质增强
            Button {
                state.isEnhancementEnabled.toggle()
                onToggleEnhancement?()
            } label: {
                Image(systemName: "sparkles")
                    .font(.system(size: 18))
                    .foregroundColor(state.isEnhancementEnabled ? .yellow : .white)
                    .symbolEffect(.bounce, value: state.isEnhancementEnabled)
            }
            .buttonStyle(.plain)

            // 全屏
            controlButton(
                state.isFullscreen ? "arrow.down.right.and.arrow.up.left" : "arrow.up.left.and.arrow.down.right",
                size: 18
            ) {
                state.isFullscreen.toggle()
                onToggleFullscreen?()
            }
            .keyboardShortcut("f", modifiers: [])
        }
    }

    // MARK: Volume Control

    private var volumeControl: some View {
        HStack(spacing: Spacing.xxs) {
            Button {
                state.isMuted.toggle()
            } label: {
                Image(systemName: volumeIcon)
                    .font(.system(size: 17))
                    .foregroundColor(.white)
            }
            .buttonStyle(.plain)

            Slider(value: $state.volume, in: 0...1)
                .frame(width: 72)
                .controlSize(.mini)
        }
    }

    // MARK: Helpers

    private func controlButton(
        _ symbol: String,
        size: CGFloat,
        tint: Color = .white,
        action: @escaping () -> Void
    ) -> some View {
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
        if state.isMuted || state.volume == 0 { return "speaker.slash.fill" }
        if state.volume < 0.4 { return "speaker.wave.1.fill" }
        if state.volume < 0.7 { return "speaker.wave.2.fill" }
        return "speaker.wave.3.fill"
    }

    private func formatTime(_ seconds: Double) -> String {
        let s = Int(seconds)
        let h = s / 3600
        let m = (s % 3600) / 60
        let sec = s % 60
        if h > 0 {
            return String(format: "%d:%02d:%02d", h, m, sec)
        } else {
            return String(format: "%02d:%02d", m, sec)
        }
    }
}

// MARK: - Preview

#Preview {
    ZStack(alignment: .bottom) {
        Color.black

        // 模拟视频画面
        Rectangle()
            .fill(
                LinearGradient(
                    colors: [.blue.opacity(0.3), .purple.opacity(0.3)],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
            )

        PlayerControls(
            state: {
                let s = PlayerState()
                s.isPlaying = true
                s.currentTime = 1935
                return s
            }()
        )
    }
    .frame(width: 900, height: 200)
    .preferredColorScheme(.dark)
}
