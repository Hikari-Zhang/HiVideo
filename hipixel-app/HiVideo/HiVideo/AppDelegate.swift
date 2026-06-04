// AppDelegate.swift — HiVideo
// NSApplicationDelegate：播放器窗口管理、文件关联

import AppKit
import PlaybackKit
import MediaKit

final class AppDelegate: NSObject, NSApplicationDelegate {

    // 应用激活时若有 .hivideo 文件则播放
    func application(_ application: NSApplication, open urls: [URL]) {
        for url in urls where isVideoFile(url) {
            openPlayer(with: url)
        }
    }

    // 从 MediaLibraryView 的 contextMenu 调用
    @objc func openPlayerWindow(_ sender: NSURL?) {
        guard let url = sender as? URL else { return }
        openPlayer(with: url)
    }

    private func openPlayer(with url: URL) {
        // 打开播放器窗口（使用 Scene ID）
        NSApp.sendAction(#selector(openPlayerScene), to: nil, from: url as NSURL)
    }

    @objc func openPlayerScene(_ sender: NSURL?) {}

    private func isVideoFile(_ url: URL) -> Bool {
        let videoExts: Set<String> = ["mp4","mkv","mov","m4v","avi","wmv","flv","webm","ts"]
        return videoExts.contains(url.pathExtension.lowercased())
    }
}
