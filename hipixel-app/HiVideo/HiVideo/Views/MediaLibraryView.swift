// MediaLibraryView.swift — HiVideo
// 媒体库内容区：网格视图 + 列表视图

import SwiftUI
import MediaKit

struct MediaLibraryView: View {
    let items: [MediaItem]
    @Binding var viewMode: MainWindowView.ViewMode
    @Binding var selectedItem: MediaItem?
    @Binding var showPlayer: Bool

    @EnvironmentObject var library: MediaLibrary
    @State private var isDragging = false

    // 网格列数：自适应 160pt 宽
    private let columns = [GridItem(.adaptive(minimum: 160, maximum: 200), spacing: 16)]

    var body: some View {
        Group {
            if items.isEmpty {
                emptyState
            } else if viewMode == .grid {
                gridView
            } else {
                listView
            }
        }
        .onDrop(of: [.fileURL], isTargeted: $isDragging) { providers in
            handleDrop(providers: providers)
        }
        .overlay(
            // 扫描中横幅
            library.isScanning ? scanningBanner : nil,
            alignment: .bottom
        )
    }

    // MARK: - Grid View

    private var gridView: some View {
        ScrollView {
            LazyVGrid(columns: columns, spacing: 16) {
                ForEach(items) { item in
                    PosterGridCell(item: item, isSelected: selectedItem?.id == item.id) {
                        selectedItem = item
                    } onPlay: {
                        play(item: item)
                    }
                }
            }
            .padding(20)
        }
    }

    // MARK: - List View

    private var listView: some View {
        List(items, selection: $selectedItem) { item in
            PosterListRow(item: item)
                .onTapGesture(count: 2) { play(item: item) }
                .contextMenu { contextMenu(for: item) }
        }
        .listStyle(.inset)
    }

    // MARK: - Empty State

    private var emptyState: some View {
        ContentUnavailableView {
            Label("没有视频", systemImage: "photo.stack")
        } description: {
            Text("拖入视频文件夹，或点击工具栏添加监视目录")
        }
    }

    // MARK: - Scanning Banner

    @ViewBuilder
    private var scanningBanner: some View {
        HStack(spacing: 8) {
            ProgressView().controlSize(.small)
            Text("正在扫描媒体库…")
                .font(.system(size: 13))
                .foregroundColor(.secondary)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(.regularMaterial)
        .clipShape(Capsule())
        .padding(.bottom, 16)
        .shadow(radius: 6)
    }

    // MARK: - Context Menu

    @ViewBuilder
    private func contextMenu(for item: MediaItem) -> some View {
        Button("播放") { play(item: item) }
        Divider()
        Button("在 Finder 中显示") {
            NSWorkspace.shared.selectFile(item.fileURL, inFileViewerRootedAtPath: "")
        }
        Divider()
        Button("从媒体库移除", role: .destructive) {
            Task { try? await library.remove(item: item) }
        }
    }

    // MARK: - Actions

    private func play(item: MediaItem) {
        selectedItem = item
        // 打开播放器窗口
        NSApp.sendAction(#selector(AppDelegate.openPlayerWindow(_:)), to: nil, from: item.url as NSURL)
        showPlayer = true
    }

    private func handleDrop(providers: [NSItemProvider]) -> Bool {
        for provider in providers {
            provider.loadItem(forTypeIdentifier: "public.file-url", options: nil) { item, _ in
                guard let data = item as? Data,
                      let url = URL(dataRepresentation: data, relativeTo: nil) else { return }
                Task { @MainActor in
                    var isDir: ObjCBool = false
                    FileManager.default.fileExists(atPath: url.path, isDirectory: &isDir)
                    if isDir.boolValue {
                        try? await self.library.addWatchFolder(url)
                    } else {
                        try? await self.library.add(fileURL: url)
                    }
                }
            }
        }
        return true
    }
}

// MARK: - PosterGridCell

struct PosterGridCell: View {
    let item: MediaItem
    let isSelected: Bool
    let onTap: () -> Void
    let onPlay: () -> Void

    @State private var isHovered = false
    @State private var thumbnail: NSImage?

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            // 海报图
            posterArt
            // 元数据
            metadata
        }
        .onHover { isHovered = $0 }
        .onTapGesture { onTap() }
        .onTapGesture(count: 2) { onPlay() }
        .animation(.spring(response: 0.28, dampingFraction: 0.85), value: isHovered)
        .task(id: item.id) { await loadThumbnail() }
    }

    private var posterArt: some View {
        ZStack(alignment: .bottom) {
            // 底图
            ZStack {
                RoundedRectangle(cornerRadius: 12)
                    .fill(Color.secondary.opacity(0.15))

                if let thumb = thumbnail {
                    Image(nsImage: thumb)
                        .resizable()
                        .aspectRatio(contentMode: .fill)
                        .clipped()
                } else {
                    Image(systemName: "film")
                        .font(.system(size: 32))
                        .foregroundColor(.secondary)
                }
            }
            .frame(width: 160, height: 240)
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(isSelected ? Color.accentColor : Color.white.opacity(0.08), lineWidth: isSelected ? 2 : 0.5)
            )

            // 续播进度条
            if item.duration > 0 && item.resumePosition > 0 {
                GeometryReader { geo in
                    ZStack(alignment: .leading) {
                        Rectangle().fill(Color.white.opacity(0.2))
                        Rectangle()
                            .fill(Color.accentColor)
                            .frame(width: geo.size.width * CGFloat(item.resumePosition / item.duration))
                    }
                }
                .frame(height: 4)
                .clipShape(RoundedRectangle(cornerRadius: 2))
            }

            // hover 播放按钮
            if isHovered {
                Circle()
                    .fill(Color.black.opacity(0.6))
                    .frame(width: 48, height: 48)
                    .overlay(Image(systemName: "play.fill").foregroundColor(.white).font(.system(size: 18)))
                    .transition(.opacity)
                    .padding(.bottom, 12)
            }
        }
        .scaleEffect(isHovered ? 1.02 : 1.0)
        .shadow(color: isHovered ? .black.opacity(0.3) : .clear, radius: isHovered ? 12 : 0, y: 4)
    }

    private var metadata: some View {
        HStack(alignment: .top) {
            VStack(alignment: .leading, spacing: 2) {
                Text(item.title)
                    .font(.system(size: 13, weight: .medium))
                    .lineLimit(1)
                Text("\(item.resolutionLabel) · \(item.durationLabel)")
                    .font(.system(size: 11))
                    .foregroundColor(.secondary)
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 2)
    }

    private func loadThumbnail() async {
        if let path = item.thumbnailPath, let img = NSImage(contentsOfFile: path) {
            thumbnail = img
            return
        }
        // 无缩略图则后台生成
        let path = await ThumbnailGenerator.generate(for: item.url, itemID: item.id)
        if let path, let img = NSImage(contentsOfFile: path) {
            thumbnail = img
        }
    }
}

// MARK: - PosterListRow

struct PosterListRow: View {
    let item: MediaItem

    var body: some View {
        HStack(spacing: 12) {
            RoundedRectangle(cornerRadius: 6)
                .fill(Color.secondary.opacity(0.15))
                .frame(width: 48, height: 72)
                .overlay(Image(systemName: "film").foregroundColor(.secondary))

            VStack(alignment: .leading, spacing: 4) {
                Text(item.title).font(.system(size: 14, weight: .medium)).lineLimit(1)
                Text("\(item.resolutionLabel) · \(item.durationLabel) · \(item.codec.uppercased())")
                    .font(.system(size: 12)).foregroundColor(.secondary)
            }
            Spacer()
            Text(fileSizeLabel)
                .font(.system(size: 12)).foregroundColor(.secondary)
        }
        .padding(.vertical, 4)
    }

    private var fileSizeLabel: String {
        let gb = Double(item.fileSize) / 1_073_741_824
        if gb >= 1 { return String(format: "%.1f GB", gb) }
        let mb = Double(item.fileSize) / 1_048_576
        return String(format: "%.0f MB", mb)
    }
}
