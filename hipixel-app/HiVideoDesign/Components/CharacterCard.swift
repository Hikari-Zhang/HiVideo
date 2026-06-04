// CharacterCard.swift — HiVideo Core Component
// Phase 0.5 · 角色卡组件
// 对应文档：docs/design/01-hivideo-core.md §10-11

import SwiftUI

// MARK: - Data Model

struct Character: Identifiable {
    let id: Int
    var name: String
    var actorName: String?       // 饰演者（真人作品）
    var alias: String?           // 别名（如 Iron Man）
    var videoCount: Int          // 出场视频数
    var clipCount: Int           // 出场片段数
    var totalDuration: TimeInterval  // 总出场时长（秒）
    var confidence: Double       // 识别置信度 0.0-1.0
    var isIdentified: Bool       // 是否已命名确认
    var thumbnailURL: URL?       // 代表性人脸图

    /// 角色名首字母（用于 initials 头像）
    var initials: String {
        let parts = name.components(separatedBy: " ")
        if parts.count >= 2 {
            return String(parts[0].prefix(1)) + String(parts[1].prefix(1))
        }
        return String(name.prefix(2)).uppercased()
    }

    /// 根据 id 派生的 initials 背景色
    var initialsColor: Color {
        Color.characterColor(for: id)
    }
}

// MARK: - Character Card (Grid View)

struct CharacterCard: View {
    let character: Character
    var onTap: (() -> Void)? = nil

    @State private var isHovered = false

    var body: some View {
        Button(action: { onTap?() }) {
            VStack(spacing: Spacing.sm) {
                avatar(size: Layout.characterAvatarMd)
                info
            }
            .padding(Spacing.md)
            .frame(width: 160)
            .background(
                RoundedRectangle(cornerRadius: Radius.lg)
                    .fill(isHovered ? Color.surfaceSecondary : Color.surfacePrimary)
                    .overlay(
                        RoundedRectangle(cornerRadius: Radius.lg)
                            .stroke(Color.borderDefault, lineWidth: 0.5)
                    )
            )
            .scaleEffect(isHovered ? 1.01 : 1.0)
            .hivShadow(isHovered ? Shadow.md : Shadow.sm)
        }
        .buttonStyle(.plain)
        .onHover { isHovered = $0 }
        .animation(HiVAnimation.default, value: isHovered)
    }

    // MARK: Info

    private var info: some View {
        VStack(spacing: 4) {
            HStack(spacing: 4) {
                Text(character.name)
                    .hivSubheadline()
                    .lineLimit(1)
                    .foregroundColor(.textPrimary)

                if character.isIdentified {
                    Image(systemName: "checkmark.seal.fill")
                        .font(.system(size: 11))
                        .foregroundColor(.accentColor)
                }
            }

            if let actor = character.actorName {
                Text(actor)
                    .hivCaption1()
                    .foregroundColor(.textSecondary)
                    .lineLimit(1)
            }

            Text("\(character.videoCount) 视频 · \(character.clipCount) 片段")
                .hivCaption2()
                .foregroundColor(.textTertiary)
        }
    }
}

// MARK: - Character Avatar

/// 独立头像组件，可在侧边栏/详情页等场景复用
struct CharacterAvatar: View {
    let character: Character
    var size: CGFloat = Layout.characterAvatarMd

    var body: some View {
        avatar(size: size)
    }
}

// MARK: - Shared Avatar Builder

private func avatar(character: Character, size: CGFloat) -> some View {
    ZStack {
        if let url = character.thumbnailURL {
            AsyncImage(url: url) { phase in
                if case .success(let img) = phase {
                    img.resizable()
                        .aspectRatio(contentMode: .fill)
                } else {
                    initialsView(character: character, size: size)
                }
            }
        } else {
            initialsView(character: character, size: size)
        }
    }
    .frame(width: size, height: size)
    .clipShape(Circle())
    .overlay(Circle().stroke(Color.borderDefault, lineWidth: 0.5))
}

private func initialsView(character: Character, size: CGFloat) -> some View {
    ZStack {
        Circle()
            .fill(character.initialsColor.opacity(0.25))

        Text(character.initials)
            .font(.system(size: size * 0.33, weight: .semibold, design: .rounded))
            .foregroundColor(character.initialsColor)
    }
}

// Extension to allow calling as method on View
extension CharacterCard {
    func avatar(size: CGFloat) -> some View {
        HiVideo_avatar(character: character, size: size)
    }
}

private struct HiVideo_avatar: View {
    let character: Character
    let size: CGFloat

    var body: some View {
        ZStack {
            if let url = character.thumbnailURL {
                AsyncImage(url: url) { phase in
                    if case .success(let img) = phase {
                        img.resizable()
                            .aspectRatio(contentMode: .fill)
                    } else {
                        fallback
                    }
                }
            } else {
                fallback
            }
        }
        .frame(width: size, height: size)
        .clipShape(Circle())
        .overlay(Circle().stroke(Color.borderDefault, lineWidth: 0.5))
    }

    private var fallback: some View {
        ZStack {
            Circle().fill(character.initialsColor.opacity(0.25))
            Text(character.initials)
                .font(.system(size: size * 0.33, weight: .semibold, design: .rounded))
                .foregroundColor(character.initialsColor)
        }
    }
}

// MARK: - Character Detail Header (详情页 Hero 区)

struct CharacterDetailHeader: View {
    let character: Character
    var onGenerateHighlight: (() -> Void)? = nil
    var onEdit: (() -> Void)? = nil
    var onDuet: (() -> Void)? = nil

    var body: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            // Hero 行
            HStack(spacing: Spacing.md) {
                HiVideo_avatar(character: character, size: Layout.characterAvatarLg)

                VStack(alignment: .leading, spacing: 4) {
                    HStack(spacing: Spacing.xs) {
                        Text(character.name)
                            .hivTitle2()
                            .foregroundColor(.textPrimary)

                        if character.isIdentified {
                            Label("已识别", systemImage: "checkmark.seal.fill")
                                .hivCaption1()
                                .foregroundColor(.accentColor)
                        }
                    }

                    if let actor = character.actorName {
                        Text("饰演者：\(actor)")
                            .hivCallout()
                            .foregroundColor(.textSecondary)
                    }

                    if let alias = character.alias {
                        Text("别名：\(alias)")
                            .hivFootnote()
                            .foregroundColor(.textTertiary)
                    }
                }
                Spacer()
            }

            // 操作按钮
            HStack(spacing: Spacing.sm) {
                actionButton("生成高光", icon: "play.circle.fill") {
                    onGenerateHighlight?()
                }
                actionButton("编辑命名", icon: "pencil") {
                    onEdit?()
                }
                actionButton("对手戏", icon: "person.2.fill", shortcut: "⌘⇧D") {
                    onDuet?()
                }
            }

            // Metric 卡片行
            metricsRow
        }
    }

    // MARK: Metrics

    private var metricsRow: some View {
        HStack(spacing: Spacing.sm) {
            metricCard(value: "\(character.videoCount)", label: "视频")
            metricCard(value: "\(character.clipCount)", label: "片段")
            metricCard(value: formatDuration(character.totalDuration), label: "时长")
            metricCard(value: "\(Int(character.confidence * 100))%", label: "置信度")
        }
    }

    private func metricCard(value: String, label: String) -> some View {
        VStack(spacing: 4) {
            Text(value)
                .hivMetric()
                .foregroundColor(.accentColor)
            Text(label)
                .hivCaption1()
                .foregroundColor(.textSecondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, Spacing.sm)
        .background(
            RoundedRectangle(cornerRadius: Radius.lg)
                .fill(Color.surfaceSecondary)
        )
    }

    private func actionButton(
        _ title: String,
        icon: String,
        shortcut: String? = nil,
        action: @escaping () -> Void
    ) -> some View {
        Button(action: action) {
            HStack(spacing: Spacing.xxs) {
                Image(systemName: icon)
                    .font(.system(size: 13))
                Text(title)
                    .hivSubheadline()
                if let sc = shortcut {
                    Text(sc)
                        .hivCaption2()
                        .foregroundColor(.textTertiary)
                }
            }
            .padding(.horizontal, Spacing.md)
            .padding(.vertical, Spacing.xs)
            .background(Color.surfaceSecondary)
            .clipShape(RoundedRectangle(cornerRadius: Radius.md))
            .overlay(
                RoundedRectangle(cornerRadius: Radius.md)
                    .stroke(Color.borderDefault, lineWidth: 0.5)
            )
        }
        .buttonStyle(.plain)
    }

    private func formatDuration(_ seconds: TimeInterval) -> String {
        let h = Int(seconds) / 3600
        let m = (Int(seconds) % 3600) / 60
        if h > 0 { return "\(h)h \(m)m" }
        return "\(m)m"
    }
}

// MARK: - Preview

#Preview("Character Grid") {
    HStack(spacing: Spacing.md) {
        CharacterCard(character: Character(
            id: 0,
            name: "Tony Stark",
            actorName: "小罗伯特·唐尼",
            alias: "Iron Man",
            videoCount: 12,
            clipCount: 46,
            totalDuration: 12240,
            confidence: 0.96,
            isIdentified: true
        ))

        CharacterCard(character: Character(
            id: 1,
            name: "宫园薰",
            videoCount: 8,
            clipCount: 23,
            totalDuration: 5820,
            confidence: 0.88,
            isIdentified: true
        ))

        // 未知角色
        CharacterCard(character: Character(
            id: 5,
            name: "未知角色",
            videoCount: 3,
            clipCount: 7,
            totalDuration: 840,
            confidence: 0,
            isIdentified: false
        ))
    }
    .padding(Spacing.xl)
    .background(Color.surfaceBackground)
    .preferredColorScheme(.dark)
}

#Preview("Character Detail Header") {
    CharacterDetailHeader(
        character: Character(
            id: 0,
            name: "Tony Stark",
            actorName: "小罗伯特·唐尼",
            alias: "Iron Man",
            videoCount: 12,
            clipCount: 46,
            totalDuration: 12240,
            confidence: 0.96,
            isIdentified: true
        )
    )
    .padding(Spacing.xl)
    .background(Color.surfaceBackground)
    .preferredColorScheme(.dark)
}
