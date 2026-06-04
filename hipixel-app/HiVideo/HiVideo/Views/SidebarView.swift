// SidebarView.swift — HiVideo
// 左侧边栏：媒体分组导航

import SwiftUI
import MediaKit

struct SidebarView: View {
    @Binding var selection: MainWindowView.SidebarItem
    @EnvironmentObject var library: MediaLibrary

    var body: some View {
        List(selection: $selection) {

            // ── 媒体库 ──
            Section("媒体库") {
                Label("全部视频", systemImage: "square.grid.2x2.fill")
                    .tag(MainWindowView.SidebarItem.allVideos)

                if !library.inProgress.isEmpty {
                    Label("在看中", systemImage: "play.circle.fill")
                        .tag(MainWindowView.SidebarItem.inProgress)
                        .badge(library.inProgress.count)
                }

                if !library.recentlyPlayed.isEmpty {
                    Label("最近播放", systemImage: "clock.fill")
                        .tag(MainWindowView.SidebarItem.recent)
                }
            }

            // ── 文件夹 ──
            if !library.watchFolders.isEmpty {
                Section("文件夹") {
                    ForEach(library.watchFolders) { folder in
                        let url = URL(fileURLWithPath: folder.path)
                        Label(url.lastPathComponent, systemImage: "externaldrive.fill")
                            .tag(MainWindowView.SidebarItem.folder(folder.path))
                    }
                }
            }
        }
        .listStyle(.sidebar)
    }
}
