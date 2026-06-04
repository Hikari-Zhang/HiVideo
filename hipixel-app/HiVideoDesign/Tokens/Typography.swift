// Typography.swift — HiVideo Design Tokens
// Phase 0.5 · SwiftUI 字体 Token
// 对应文档：docs/design/00-tokens.md §2

import SwiftUI

// MARK: - Type Scale

extension Font {

    // MARK: Display (≥ 20pt, SF Pro Display)
    /// 页面大标题（启动屏 Hero）
    static var hivLargeTitle: Font {
        .system(size: 34, weight: .regular, design: .default)
    }
    /// 一级标题
    static var hivTitle1: Font {
        .system(size: 28, weight: .regular, design: .default)
    }
    /// 二级标题（卡片标题）
    static var hivTitle2: Font {
        .system(size: 22, weight: .regular, design: .default)
    }
    /// 三级标题（浮窗标题）
    static var hivTitle3: Font {
        .system(size: 20, weight: .regular, design: .default)
    }

    // MARK: Text (< 20pt, SF Pro Text)
    /// 强调标签
    static var hivHeadline: Font {
        .system(size: 17, weight: .semibold, design: .default)
    }
    /// 正文、描述
    static var hivBody: Font {
        .system(size: 17, weight: .regular, design: .default)
    }
    /// 次级正文
    static var hivCallout: Font {
        .system(size: 16, weight: .regular, design: .default)
    }
    /// 列表副标题
    static var hivSubheadline: Font {
        .system(size: 15, weight: .regular, design: .default)
    }
    /// 元数据、说明
    static var hivFootnote: Font {
        .system(size: 13, weight: .regular, design: .default)
    }
    /// 时间码、路径
    static var hivCaption1: Font {
        .system(size: 12, weight: .regular, design: .default)
    }
    /// 最小徽章文字
    static var hivCaption2: Font {
        .system(size: 11, weight: .regular, design: .default)
    }

    // MARK: Numeric (SF Pro Rounded)
    /// 时间码（HH:MM:SS）
    static var hivTimecode: Font {
        .system(size: 13, weight: .medium, design: .rounded)
    }
    /// 进度/计数器
    static var hivCounter: Font {
        .system(size: 15, weight: .semibold, design: .rounded)
    }
    /// 大数字（详情页统计数据）
    static var hivMetric: Font {
        .system(size: 28, weight: .bold, design: .rounded)
    }

    // MARK: Monospaced (SF Mono)
    /// 文件路径、日志
    static var hivMono: Font {
        .system(size: 12, weight: .regular, design: .monospaced)
    }
}

// MARK: - View Modifier Helpers

extension View {
    func hivLargeTitle()    -> some View { font(.hivLargeTitle) }
    func hivTitle1()        -> some View { font(.hivTitle1) }
    func hivTitle2()        -> some View { font(.hivTitle2) }
    func hivTitle3()        -> some View { font(.hivTitle3) }
    func hivHeadline()      -> some View { font(.hivHeadline) }
    func hivBody()          -> some View { font(.hivBody) }
    func hivCallout()       -> some View { font(.hivCallout) }
    func hivSubheadline()   -> some View { font(.hivSubheadline) }
    func hivFootnote()      -> some View { font(.hivFootnote) }
    func hivCaption1()      -> some View { font(.hivCaption1) }
    func hivCaption2()      -> some View { font(.hivCaption2) }
    func hivTimecode()      -> some View { font(.hivTimecode) }
    func hivCounter()       -> some View { font(.hivCounter) }
    func hivMetric()        -> some View { font(.hivMetric) }
    func hivMono()          -> some View { font(.hivMono) }
}
