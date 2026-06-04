// RootView.swift — HiVideo
// 根视图：启动屏 vs 主窗口切换

import SwiftUI
import MediaKit

struct RootView: View {
    @Binding var showPlayer: Bool
    @EnvironmentObject var library: MediaLibrary

    var body: some View {
        Group {
            if library.items.isEmpty && library.watchFolders.isEmpty {
                LaunchView()
            } else {
                MainWindowView(showPlayer: $showPlayer)
            }
        }
        .animation(.spring(response: 0.35, dampingFraction: 0.8), value: library.items.isEmpty)
    }
}
