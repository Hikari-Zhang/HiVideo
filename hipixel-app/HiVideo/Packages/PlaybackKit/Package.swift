// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "PlaybackKit",
    platforms: [.macOS(.v14)],
    products: [
        .library(name: "PlaybackKit", targets: ["PlaybackKit"]),
    ],
    dependencies: [],
    targets: [
        .target(
            name: "PlaybackKit",
            dependencies: [],
            swiftSettings: [
                .enableUpcomingFeature("BareSlashRegexLiterals"),
                .enableExperimentalFeature("StrictConcurrency"),
            ]
        ),
        .testTarget(
            name: "PlaybackKitTests",
            dependencies: ["PlaybackKit"]
        ),
    ]
)
