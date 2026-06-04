// PosterCard.swift — HiVideo Core Component
// Phase 0.5 · 海报卡组件
// 对应文档：docs/design/01-hivideo-core.md §3

import SwiftUI

// MARK: - Data Model

struct MediaItem: Identifiable {
    let id: Int
    var title: String
    var subtitle: String          // 年份/分辨率/时长
    var posterURL: URL?
    var progress: Double          // 0.0 – 1.0，0 = 未看
    var variantCount: Int         // 副本数
    var isSelected: Bool = false
}

// MARK: - PosterCard

struct PosterCard: View {
    let item: MediaItem
    var size: PosterSize = .medium
    var onTap: (() -> Void)? = nil
    var onSelect: (() -> Void)? = nil
    var isInSelectionMode: Bool = false

    @State private var isHovered = false

    var body: some View {
        VStack(alignment: .leading, spacing: Spacing.xs) {
            posterImage
            metadata
        }
        .frame(width: size.width)
        .onHover { isHovered = $0 }
        .onTapGesture { onTap?() }
        .animation(HiVAnimation.default, value: isHovered)
    }

    // MARK: Poster Image

    private var posterImage: some View {
        ZStack(alignment: .bottom) {
            // 海报图
            AsyncImage(url: item.posterURL) { phase in
                switch phase {
                case .success(let img):
                    img.resizable().aspectRatio(contentMode: .fill)
                case .failure:
                    posterPlaceholder
                case .empty:
                    posterPlaceholder
                @unknown default:
                    posterPlaceholder
                }
            }
            .frame(width: size.width, height: size.height)
            .clipped()

            // 进度条叠层
            if item.progress > 0 {
                progressBar
            }

            // 悬停播放按钮叠层
            if isHovered {
                playOverlay
            }

            // 批量选择框
            if isInSelectionMode {
                selectionBox
            }
        }
        .frame(width: size.width, height: size.height)
        .clipShape(RoundedRectangle(cornerRadius: Radius.lg))
        .overlay(
            RoundedRectangle(cornerRadius: Radius.lg)
                .stroke(Color.borderDefault, lineWidth: 0.5)
        )
        .scaleEffect(isHovered ? 1.02 : 1.0)
        .hivShadow(isHovered ? Shadow.md : Shadow.sm)
    }

    private var posterPlaceholder: some View {
        ZStack {
            Color.surfaceSecondary
            Image(systemName: "film")
                .font(.system(size: 32))
                .foregroundColor(.textTertiary)
        }
    }

    private var progressBar: some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                Rectangle()
                    .fill(Color.white.opacity(0.2))
                    .frame(height: 4)
                Rectangle()
                    .fill(Color.accentColor)
                    .frame(width: geo.size.width * item.progress, height: 4)
            }
        }
        .frame(height: 4)
    }

    private var playOverlay: some View {
        Image(systemName: "play.circle.fill")
            .font(.system(size: 56))
            .foregroundColor(.white.opacity(0.7))
            .transition(.opacity)
    }

    private var selectionBox: some View {
        VStack {
            HStack {
                ZStack {
                    Circle()
                        .fill(item.isSelected ? Color.accentColor : Color.white.opacity(0.8))
                        .frame(width: 22, height: 22)
                    if item.isSelected {
                        Image(systemName: "checkmark")
                            .font(.system(size: 11, weight: .bold))
                            .foregroundColor(.white)
                    }
                }
                .padding(Spacing.xs)
                .onTapGesture { onSelect?() }
                Spacer()
            }
            Spacer()
        }
    }

    // MARK: Metadata

    private var metadata: some View {
        HStack(alignment: .top) {
            VStack(alignment: .leading, spacing: 2) {
                Text(item.title)
                    .hivSubheadline()
                    .lineLimit(1)
                    .foregroundColor(.textPrimary)

                Text(item.subtitle)
                    .hivCaption1()
                    .foregroundColor(.textSecondary)
            }

            Spacer(minLength: 0)

            // 副本数徽章
            if item.variantCount >= 2 {
                variantBadge
            }
        }
        .padding(.horizontal, 2)
    }

    private var variantBadge: some View {
        Text("\(item.variantCount)")
            .hivCaption2()
            .foregroundColor(.white)
            .padding(.horizontal, Spacing.xxs)
            .padding(.vertical, 2)
            .background(Color.accentColor)
            .clipShape(Capsule())
    }
}

// MARK: - Poster Size

enum PosterSize {
    case small, medium, large, xlarge

    var width: CGFloat {
        switch self {
        case .small:  return 120
        case .medium: return 160
        case .large:  return 200
        case .xlarge: return 240
        }
    }

    var height: CGFloat { width * 1.5 } // 2:3 比例
}

// MARK: - Preview

#Preview {
    HStack(spacing: Spacing.md) {
        PosterCard(
            item: MediaItem(
                id: 1,
                title: "四月是你的谎言",
                subtitle: "2024 · 1080p",
                progress: 0.35,
                variantCount: 2
            )
        )
        PosterCard(
            item: MediaItem(
                id: 2,
                title: "复仇者联盟",
                subtitle: "2012 · 4K HDR",
                progress: 0,
                variantCount: 1
            )
        )
    }
    .padding(Spacing.xl)
    .background(Color.surfaceBackground)
    .preferredColorScheme(.dark)
}
