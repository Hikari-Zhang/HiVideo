// HiVideoApp.swift — HiVideo
// 应用入口，窗口配置，菜单命令

import SwiftUI
import UniformTypeIdentifiers
import PlaybackKit
import MediaKit

@main
struct HiVideoApp: App {

    // MARK: - Shared State

    @StateObject private var library: MediaLibrary = {
        (try? MediaLibrary()) ?? MediaLibrary(db: try! AppDatabase.makeDatabaseQueue(at: ":memory:"))
    }()

    @StateObject private var player = HiVideoPlayer()
    @StateObject private var playerState = PlayerStateObject()
    @State private var showPlayer = false

    // MARK: - Scene

    var body: some Scene {
        WindowGroup {
            RootView(showPlayer: $showPlayer)
                .environmentObject(library)
                .environmentObject(player)
                .environmentObject(playerState)
                .frame(minWidth: 900, minHeight: 600)
        }
        .windowStyle(.hiddenTitleBar)
        .windowToolbarStyle(.unified(showsTitle: false))
        .commands {
            HiVideoCommands(library: library, showPlayer: $showPlayer)
        }

        // 独立播放器窗口（全屏沉浸式）
        Window("播放器", id: "player") {
            PlayerWindowView()
                .environmentObject(player)
                .environmentObject(playerState)
        }
        .windowStyle(.hiddenTitleBar)
        .windowResizability(.contentMinSize)
    }
}

// MARK: - Commands

struct HiVideoCommands: Commands {
    let library: MediaLibrary
    @Binding var showPlayer: Bool

    var body: some Commands {
        CommandGroup(replacing: .newItem) {
            Button("打开文件…") {
                openFile()
            }
            .keyboardShortcut("o")

            Button("打开文件夹…") {
                openFolder()
            }
            .keyboardShortcut("o", modifiers: [.command, .shift])
        }
    }

    private func openFile() {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = false
        panel.allowedContentTypes = [.movie, .video, .mpeg4Movie, .quickTimeMovie]
        if panel.runModal() == .OK, let url = panel.url {
            Task { try? await library.add(fileURL: url) }
        }
    }

    private func openFolder() {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        if panel.runModal() == .OK, let url = panel.url {
            Task { try? await library.addWatchFolder(url) }
        }
    }
}
