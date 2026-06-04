// swift-tools-version: 5.9
// AIKit — Phase 3 stub（AI 字幕、画质增强、分类等，Phase 1 暂不实现）
import PackageDescription

let package = Package(
    name: "AIKit",
    platforms: [.macOS(.v14)],
    products: [
        .library(name: "AIKit", targets: ["AIKit"]),
    ],
    targets: [
        .target(name: "AIKit", dependencies: []),
    ]
)
