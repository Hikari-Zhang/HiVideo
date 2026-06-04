// MediaDetailView.swift — HiVideo
// 右侧详情面板：海报 + 元数据 + 4个 Tab（简介/副本/摘要/章节）

import SwiftUI
import MediaKit

struct MediaDetailView: View {
    let item: MediaItem

    @EnvironmentObject var library: MediaLibrary
    @State private var selectedTab: DetailTab = .info
    @State private var thumbnail: NSImage?

    enum DetailTab: String, CaseIterable {
        case info = "简介"
        case variants = "副本"
        case summary = "摘要"
        case chapters = "章节"
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {

                // 海报
                poster
                    .padding(.horizontal, 16)
                    .padding(.top, 20)

                // 标题 + 元数据
                VStack(alignment: .leading, spacing: 6) {
                    Text(item.title)
                        .font(.system(size: 17, weight: .semibold))
                        .lineLimit(2)

                    Text(subtitleText)
                        .font(.system(size: 12))
                        .foregroundColor(.secondary)
                }
                .padding(.horizontal, 16)
                .padding(.top, 12)

                // Tab Bar
                HStack(spacing: 0) {
                    ForEach(DetailTab.allCases, id: \.self) { tab in
                        Button(tab.rawValue) { selectedTab = tab }
                            .buttonStyle(.plain)
                            .font(.system(size: 13))
                            .foregroundColor(selectedTab == tab ? .accentColor : .secondary)
                            .padding(.vertical, 10)
                            .padding(.horizontal, 12)
                            .overlay(
                                Rectangle()
                                    .fill(selectedTab == tab ? Color.accentColor : .clear)
                                    .frame(height: 2),
                                alignment: .bottom
                            )
                    }
                }
                .overlay(Rectangle().fill(Color.secondary.opacity(0.2)).frame(height: 0.5), alignment: .bottom)
                .padding(.top, 12)

                // Tab Content
                Group {
                    switch selectedTab {
                    case .info:     infoTab
                    case .variants: variantsTab
                    case .summary:  summaryTab
                    case .chapters: chaptersTab
                    }
                }
                .padding(.horizontal, 16)
                .padding(.top, 12)
            }
        }
        .task(id: item.id) { await loadThumbnail() }
    }

    // MARK: - Poster

    private var poster: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 12)
                .fill(Color.secondary.opacity(0.15))
                .aspectRatio(2/3, contentMode: .fit)

            if let thumb = thumbnail {
                Image(nsImage: thumb)
                    .resizable()
                    .aspectRatio(contentMode: .fill)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
            } else {
                Image(systemName: "film")
                    .font(.system(size: 40))
                    .foregroundColor(.secondary)
            }
        }
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color.white.opacity(0.08), lineWidth: 0.5))
        .shadow(color: .black.opacity(0.2), radius: 8, y: 4)
    }

    // MARK: - Info Tab

    private var infoTab: some View {
        VStack(spacing: 0) {
            infoRow("分辨率", "\(item.width)×\(item.height) (\(item.resolutionLabel))")
            infoRow("时长", item.durationLabel)
            infoRow("编码", item.codec.uppercased())
            infoRow("大小", fileSizeLabel)
            infoRow("路径", URL(fileURLWithPath: item.fileURL).deletingLastPathComponent().path)
            if item.resumePosition > 0 {
                infoRow("续播", item.formattedResumePosition)
            }
        }
        .padding(.bottom, 20)
    }

    private func infoRow(_ key: String, _ value: String) -> some View {
        HStack(alignment: .top) {
            Text(key)
                .font(.system(size: 13))
                .foregroundColor(.secondary)
                .frame(width: 60, alignment: .leading)
            Text(value)
                .font(.system(size: 13))
                .foregroundColor(.primary)
                .lineLimit(2)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(.vertical, 6)
        .overlay(Rectangle().fill(Color.secondary.opacity(0.15)).frame(height: 0.5), alignment: .bottom)
    }

    // MARK: - Variants Tab (Phase 7 实现，当前占位)

    private var variantsTab: some View {
        VStack {
            Image(systemName: "doc.on.doc")
                .font(.system(size: 36))
                .foregroundColor(.secondary)
                .padding(.top, 20)
            Text("副本管理")
                .font(.system(size: 15, weight: .medium))
                .padding(.top, 8)
            Text("Phase 7 将支持多副本合并与管理")
                .font(.system(size: 13))
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
                .padding(.top, 4)
        }
        .frame(maxWidth: .infinity)
        .padding(.bottom, 20)
    }

    // MARK: - Summary Tab (Phase 3 实现)

    private var summaryTab: some View {
        VStack(spacing: 12) {
            Image(systemName: "text.document")
                .font(.system(size: 36))
                .foregroundColor(.secondary)
                .padding(.top, 20)
            Text("AI 摘要")
                .font(.system(size: 15, weight: .medium))
            Text("⌘U 一键生成视频摘要")
                .font(.system(size: 13))
                .foregroundColor(.secondary)
            Button("生成摘要") {}
                .buttonStyle(.bordered)
                .tint(.accentColor)
                .disabled(true)  // Phase 3 实现
        }
        .frame(maxWidth: .infinity)
        .padding(.bottom, 20)
    }

    // MARK: - Chapters Tab (Phase 3 实现)

    private var chaptersTab: some View {
        VStack {
            Image(systemName: "list.number")
                .font(.system(size: 36))
                .foregroundColor(.secondary)
                .padding(.top, 20)
            Text("章节")
                .font(.system(size: 15, weight: .medium))
                .padding(.top, 8)
            Text("Phase 3 将自动识别章节时间点")
                .font(.system(size: 13))
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.bottom, 20)
    }

    // MARK: - Helpers

    private var subtitleText: String {
        var parts: [String] = []
        if item.duration > 0 { parts.append(item.durationLabel) }
        if !item.resolutionLabel.isEmpty { parts.append(item.resolutionLabel) }
        if !item.codec.isEmpty { parts.append(item.codec.uppercased()) }
        return parts.joined(separator: " · ")
    }

    private var fileSizeLabel: String {
        let gb = Double(item.fileSize) / 1_073_741_824
        if gb >= 1 { return String(format: "%.2f GB", gb) }
        let mb = Double(item.fileSize) / 1_048_576
        return String(format: "%.0f MB", mb)
    }

    private func loadThumbnail() async {
        // 1. 数据库路径
        if let path = item.thumbnailPath, !path.isEmpty,
           let img = NSImage(contentsOfFile: path) {
            thumbnail = img; return
        }
        // 2. 缓存目录直接查找
        let cacheURL = FileManager.default
            .urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("HiVideo/Thumbnails/\(item.id).jpg")
        if let img = NSImage(contentsOf: cacheURL) {
            thumbnail = img; return
        }
        // 3. 触发生成
        if let path = await ThumbnailGenerator.generate(for: item.url, itemID: item.id),
           let img = NSImage(contentsOfFile: path) {
            thumbnail = img
        }
    }
}

// Extension on MediaItem for formatted resume position
extension MediaItem {
    var formattedResumePosition: String {
        let s = Int(resumePosition)
        let h = s / 3600, m = (s % 3600) / 60, sec = s % 60
        if h > 0 { return String(format: "%d:%02d:%02d", h, m, sec) }
        return String(format: "%02d:%02d", m, sec)
    }
}
