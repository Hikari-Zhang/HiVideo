// CommandPalette.swift — HiVideo Core Component
// Phase 0.5 · ⌘K 命令面板
// 对应文档：docs/design/01-hivideo-core.md §8

import SwiftUI

// MARK: - Data Models

struct CommandItem: Identifiable {
    let id = UUID()
    var title: String
    var subtitle: String?
    var icon: String             // SF Symbol name
    var shortcut: String?        // 显示用快捷键文字，如 "⌘J"
    var group: CommandGroup
    var action: () -> Void

    enum CommandGroup: String, CaseIterable {
        case recent     = "最近使用"
        case video      = "视频"
        case character  = "角色"
        case action     = "操作"
        case settings   = "设置"
    }
}

// MARK: - Command Palette

struct CommandPalette: View {
    @Binding var isPresented: Bool
    var items: [CommandItem]
    var onSearch: ((String) -> [CommandItem])? = nil

    @State private var query = ""
    @State private var selectedIndex = 0
    @FocusState private var searchFocused: Bool

    private var filteredGroups: [(CommandItem.CommandGroup, [CommandItem])] {
        let results = query.isEmpty ? items : (onSearch?(query) ?? items.filter {
            $0.title.localizedCaseInsensitiveContains(query) ||
            ($0.subtitle?.localizedCaseInsensitiveContains(query) ?? false)
        })
        return CommandItem.CommandGroup.allCases.compactMap { group in
            let groupItems = results.filter { $0.group == group }
            return groupItems.isEmpty ? nil : (group, groupItems)
        }
    }

    private var allFilteredItems: [CommandItem] {
        filteredGroups.flatMap { $0.1 }
    }

    var body: some View {
        ZStack {
            // 背景遮罩
            Color.black.opacity(0.4)
                .ignoresSafeArea()
                .onTapGesture { dismiss() }

            // 面板主体
            VStack(spacing: 0) {
                searchBar
                Divider().opacity(0.3)
                resultsList
            }
            .frame(maxWidth: Layout.commandPaletteMaxWidth)
            .frame(maxHeight: Layout.commandPaletteMaxHeight)
            .background {
                #if os(macOS)
                VisualEffectView.menu
                    .clipShape(RoundedRectangle(cornerRadius: Radius.xl))
                #else
                RoundedRectangle(cornerRadius: Radius.xl)
                    .fill(Color.surfaceElevated)
                #endif
            }
            .clipShape(RoundedRectangle(cornerRadius: Radius.xl))
            .hivShadow(Shadow.lg)
            .scaleEffect(isPresented ? 1.0 : 0.96)
            .opacity(isPresented ? 1.0 : 0.0)
        }
        .onAppear {
            searchFocused = true
        }
        .onKeyPress(.escape) {
            dismiss()
            return .handled
        }
        .onKeyPress(.upArrow) {
            moveSelection(by: -1)
            return .handled
        }
        .onKeyPress(.downArrow) {
            moveSelection(by: 1)
            return .handled
        }
        .onKeyPress(.return) {
            executeSelected()
            return .handled
        }
    }

    // MARK: Search Bar

    private var searchBar: some View {
        HStack(spacing: Spacing.sm) {
            Image(systemName: "magnifyingglass")
                .foregroundColor(.textSecondary)
                .font(.system(size: 18))

            TextField("搜索或输入命令…", text: $query)
                .hivBody()
                .textFieldStyle(.plain)
                .focused($searchFocused)
                .onChange(of: query) { _ in selectedIndex = 0 }

            if !query.isEmpty {
                Button {
                    query = ""
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundColor(.textTertiary)
                }
                .buttonStyle(.plain)
            }
        }
        .padding(.horizontal, Spacing.md)
        .frame(height: 52)
    }

    // MARK: Results List

    private var resultsList: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 0, pinnedViews: .sectionHeaders) {
                ForEach(filteredGroups, id: \.0) { group, items in
                    Section {
                        ForEach(Array(items.enumerated()), id: \.element.id) { idx, item in
                            let globalIdx = allFilteredItems.firstIndex(where: { $0.id == item.id }) ?? 0
                            CommandRow(
                                item: item,
                                isSelected: selectedIndex == globalIdx
                            ) {
                                item.action()
                                dismiss()
                            }
                        }
                    } header: {
                        groupHeader(group.rawValue)
                    }
                }

                if allFilteredItems.isEmpty {
                    emptyState
                }
            }
            .padding(.vertical, Spacing.xs)
        }
    }

    private func groupHeader(_ title: String) -> some View {
        Text(title.uppercased())
            .hivCaption1()
            .foregroundColor(.textTertiary)
            .padding(.horizontal, Spacing.md)
            .padding(.vertical, Spacing.xs)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color.surfaceElevated.opacity(0.8))
    }

    private var emptyState: some View {
        VStack(spacing: Spacing.sm) {
            Image(systemName: "magnifyingglass")
                .font(.system(size: 32))
                .foregroundColor(.textTertiary)
            Text("没有找到「\(query)」相关内容")
                .hivCallout()
                .foregroundColor(.textTertiary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, Spacing.xxxl)
    }

    // MARK: Actions

    private func dismiss() {
        withAnimation(HiVAnimation.modal) {
            isPresented = false
        }
    }

    private func moveSelection(by delta: Int) {
        let count = allFilteredItems.count
        guard count > 0 else { return }
        selectedIndex = (selectedIndex + delta + count) % count
    }

    private func executeSelected() {
        guard selectedIndex < allFilteredItems.count else { return }
        allFilteredItems[selectedIndex].action()
        dismiss()
    }
}

// MARK: - Command Row

private struct CommandRow: View {
    let item: CommandItem
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: Spacing.sm) {
                Image(systemName: item.icon)
                    .font(.system(size: 16))
                    .foregroundColor(isSelected ? .accentColor : .textSecondary)
                    .frame(width: 20)

                VStack(alignment: .leading, spacing: 2) {
                    Text(item.title)
                        .hivCallout()
                        .foregroundColor(.textPrimary)

                    if let subtitle = item.subtitle {
                        Text(subtitle)
                            .hivCaption1()
                            .foregroundColor(.textSecondary)
                    }
                }

                Spacer()

                if let shortcut = item.shortcut {
                    Text(shortcut)
                        .hivCaption1()
                        .foregroundColor(.textTertiary)
                        .padding(.horizontal, Spacing.xs)
                        .padding(.vertical, 3)
                        .background(Color.surfaceSecondary)
                        .clipShape(RoundedRectangle(cornerRadius: Radius.sm))
                }
            }
            .padding(.horizontal, Spacing.md)
            .frame(height: 44)
            .background(isSelected ? Color.stateSelected : Color.clear)
            .clipShape(RoundedRectangle(cornerRadius: Radius.md))
            .padding(.horizontal, Spacing.xs)
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Preview

#Preview {
    CommandPalette(
        isPresented: .constant(true),
        items: [
            CommandItem(title: "继续播放「四月是你的谎言 E02」",
                       icon: "play.fill",
                       shortcut: nil,
                       group: .recent,
                       action: {}),
            CommandItem(title: "生成字幕",
                       subtitle: "使用 Whisper 本地生成",
                       icon: "captions.bubble.fill",
                       shortcut: "⌘J",
                       group: .action,
                       action: {}),
            CommandItem(title: "画质增强",
                       icon: "sparkles",
                       shortcut: "⌘E",
                       group: .action,
                       action: {}),
        ]
    )
    .frame(width: 800, height: 600)
    .background(Color.surfaceBackground)
    .preferredColorScheme(.dark)
}
