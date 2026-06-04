// LaunchView.swift — HiVideo
// 启动屏：Logo + 拖入提示 + 最近播放
// 参考设计稿：docs/design/mockups/01-launch.html

import SwiftUI
import MediaKit

struct LaunchView: View {
    @EnvironmentObject var library: MediaLibrary
    @State private var isDragging = false

    var body: some View {
        ZStack {
            // 背景渐变
            RadialGradient(
                colors: [Color.accentColor.opacity(0.05), Color.black.opacity(0.02)],
                center: .init(x: 0.5, y: 0.35),
                startRadius: 0,
                endRadius: 400
            )
            .ignoresSafeArea()

            VStack(spacing: 32) {
                Spacer()

                // App 图标 + 名称
                VStack(spacing: 12) {
                    RoundedRectangle(cornerRadius: 18)
                        .fill(
                            LinearGradient(
                                colors: [.accentColor, Color.purple],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                        )
                        .frame(width: 80, height: 80)
                        .overlay(
                            Image(systemName: "play.fill")
                                .font(.system(size: 36))
                                .foregroundColor(.white)
                        )
                        .shadow(color: .accentColor.opacity(0.4), radius: 16, y: 6)

                    Text("HiVideo")
                        .font(.system(size: 34, weight: .light, design: .default))

                    Text("打开就能用，看完就懂你")
                        .font(.system(size: 16))
                        .foregroundColor(.secondary)
                }

                // 拖放区
                dropZone

                // 最近播放
                if !library.recentlyPlayed.isEmpty {
                    recentSection
                }

                Spacer()
            }
            .padding(.horizontal, 48)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .onDrop(of: [.fileURL], isTargeted: $isDragging) { providers in
            handleDrop(providers: providers)
        }
    }

    // MARK: - Drop Zone

    private var dropZone: some View {
        VStack(spacing: 10) {
            Image(systemName: "arrow.up.doc")
                .font(.system(size: 28))
                .foregroundColor(.secondary)

            Text("拖入视频文件或文件夹")
                .font(.system(size: 15, weight: .medium))

            Text("支持 MKV、MP4、MOV、AVI 等主流格式")
                .font(.system(size: 13))
                .foregroundColor(.secondary)

            Button("⌘O  选择文件") {
                openFile()
            }
            .buttonStyle(.plain)
            .font(.system(size: 12))
            .foregroundColor(.secondary)
            .padding(.vertical, 4)
            .padding(.horizontal, 12)
            .background(Color.secondary.opacity(0.1))
            .clipShape(Capsule())
        }
        .padding(.vertical, 28)
        .padding(.horizontal, 56)
        .overlay(
            RoundedRectangle(cornerRadius: 18)
                .strokeBorder(
                    isDragging ? Color.accentColor : Color.secondary.opacity(0.3),
                    style: StrokeStyle(lineWidth: 1.5, dash: [6, 4])
                )
        )
        .background(
            RoundedRectangle(cornerRadius: 18)
                .fill(isDragging ? Color.accentColor.opacity(0.05) : Color.clear)
        )
        .animation(.spring(response: 0.2, dampingFraction: 0.85), value: isDragging)
    }

    // MARK: - Recent Section

    private var recentSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("最近播放")
                .font(.system(size: 11, weight: .semibold))
                .foregroundColor(.secondary)
                .textCase(.uppercase)
                .tracking(0.8)

            HStack(spacing: 12) {
                ForEach(library.recentlyPlayed.prefix(3)) { item in
                    SmallPosterCard(item: item)
                }
            }
        }
    }

    // MARK: - Actions

    private func openFile() {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = true
        panel.canChooseDirectories = true
        panel.allowedContentTypes = [.movie, .video]
        guard panel.runModal() == .OK else { return }
        Task {
            for url in panel.urls {
                var isDir: ObjCBool = false
                if FileManager.default.fileExists(atPath: url.path, isDirectory: &isDir) {
                    if isDir.boolValue {
                        try? await library.addWatchFolder(url)
                    } else {
                        try? await library.add(fileURL: url)
                    }
                }
            }
        }
    }

    private func handleDrop(providers: [NSItemProvider]) -> Bool {
        for provider in providers {
            provider.loadItem(forTypeIdentifier: "public.file-url", options: nil) { item, _ in
                guard let data = item as? Data,
                      let url = URL(dataRepresentation: data, relativeTo: nil) else { return }
                Task { @MainActor in
                    var isDir: ObjCBool = false
                    if FileManager.default.fileExists(atPath: url.path, isDirectory: &isDir) {
                        if isDir.boolValue {
                            try? await self.library.addWatchFolder(url)
                        } else {
                            try? await self.library.add(fileURL: url)
                        }
                    }
                }
            }
        }
        return true
    }
}

// MARK: - SmallPosterCard

private struct SmallPosterCard: View {
    let item: MediaItem
    @State private var thumbnail: NSImage?

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            ZStack {
                RoundedRectangle(cornerRadius: 8)
                    .fill(Color.secondary.opacity(0.15))
                    .frame(width: 80, height: 120)

                if let thumb = thumbnail {
                    Image(nsImage: thumb)
                        .resizable()
                        .aspectRatio(contentMode: .fill)
                        .frame(width: 80, height: 120)
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                } else {
                    Image(systemName: "film")
                        .font(.system(size: 24))
                        .foregroundColor(.secondary)
                }
            }

            Text(item.title)
                .font(.system(size: 11))
                .lineLimit(1)
                .frame(width: 80, alignment: .leading)
        }
        .task {
            if let path = item.thumbnailPath {
                thumbnail = NSImage(contentsOfFile: path)
            }
        }
    }
}
