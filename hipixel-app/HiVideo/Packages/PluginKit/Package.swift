// swift-tools-version: 5.9
// PluginKit — Phase 9 stub（插件 SDK，Phase 1 暂不实现）
import PackageDescription

let package = Package(
    name: "PluginKit",
    platforms: [.macOS(.v14)],
    products: [
        .library(name: "PluginKit", targets: ["PluginKit"]),
    ],
    targets: [
        .target(name: "PluginKit", dependencies: []),
    ]
)
