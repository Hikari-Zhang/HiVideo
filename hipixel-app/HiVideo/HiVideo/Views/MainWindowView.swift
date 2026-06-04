// MainWindowView.swift — HiVideo
// 主窗口：三栏 NavigationSplitView（侧边栏 + 媒体库 + 详情面板）
// 布局常量来自 HiVideoDesign/Tokens/Spacing.swift Layout.*

import SwiftUI
import MediaKit

struct MainWindowView: View {
    @Binding var showPlayer: Bool
    @EnvironmentObject var library: MediaLibrary

    @State private var selectedItem: MediaItem? = nil
    @State private var viewMode: ViewMode = .grid
    @State private var sidebarSelection: SidebarItem = .allVideos
    @State private var showDetailPanel = true

    enum ViewMode { case grid, list }
    enum SidebarItem: Hashable {
        case allVideos, inProgress, recent
        case folder(String)  // folder path
    }

    var body: some View {
        NavigationSplitView(
            columnVisibility: .constant(.all)
        ) {
            // ── 左：侧边栏 ──
            SidebarView(selection: $sidebarSelection)
                .navigationSplitViewColumnWidth(min: 180, ideal: 240, max: 300)

        } content: {
            // ── 中：媒体库内容 ──
            MediaLibraryView(
                items: filteredItems,
                viewMode: $viewMode,
                selectedItem: $selectedItem,
                showPlayer: $showPlayer
            )
            .navigationSplitViewColumnWidth(min: 400, ideal: 700)
            .toolbar {
                toolbarContent
            }

        } detail: {
            // ── 右：详情面板 ──
            if let item = selectedItem {
                MediaDetailView(item: item)
                    .navigationSplitViewColumnWidth(min: 280, ideal: 320, max: 400)
            } else {
                ContentUnavailableView("选择一个视频", systemImage: "film", description: Text("点击媒体库中的视频查看详情"))
                    .navigationSplitViewColumnWidth(min: 280, ideal: 320)
            }
        }
        .navigationSplitViewStyle(.balanced)
    }

    // MARK: - Filtered Items

    private var filteredItems: [MediaItem] {
        switch sidebarSelection {
        case .allVideos:    return library.items
        case .inProgress:  return library.inProgress
        case .recent:      return library.recentlyPlayed
        case .folder(let path):
            return library.items.filter { $0.fileURL.hasPrefix(path) }
        }
    }

    // MARK: - Toolbar

    @ToolbarContentBuilder
    private var toolbarContent: some ToolbarContent {
        ToolbarItemGroup(placement: .navigation) {
            // 视图切换
            Picker("视图", selection: $viewMode) {
                Image(systemName: "square.grid.2x2").tag(ViewMode.grid)
                Image(systemName: "list.bullet").tag(ViewMode.list)
            }
            .pickerStyle(.segmented)
            .frame(width: 72)
        }

        ToolbarItemGroup(placement: .primaryAction) {
            // 添加文件夹
            Button {
                addFolder()
            } label: {
                Image(systemName: "folder.badge.plus")
            }
            .help("添加监视文件夹")

            // 重新扫描
            Button {
                Task { await library.rescanAll() }
            } label: {
                Image(systemName: library.isScanning ? "arrow.2.circlepath" : "arrow.clockwise")
            }
            .help("重新扫描所有文件夹")
            .symbolEffect(.rotate, isActive: library.isScanning)
        }
    }

    // MARK: - Actions

    private func addFolder() {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.prompt = "添加"
        guard panel.runModal() == .OK, let url = panel.url else { return }
        Task { try? await library.addWatchFolder(url) }
    }
}
