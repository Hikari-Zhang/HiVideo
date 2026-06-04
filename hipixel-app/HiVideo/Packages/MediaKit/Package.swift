// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "MediaKit",
    platforms: [.macOS(.v14)],
    products: [
        .library(name: "MediaKit", targets: ["MediaKit"]),
    ],
    dependencies: [
        // GRDB.swift — SQLite ORM
        .package(url: "https://github.com/groue/GRDB.swift.git", from: "6.0.0"),
    ],
    targets: [
        .target(
            name: "MediaKit",
            dependencies: [
                .product(name: "GRDB", package: "GRDB.swift"),
            ],
            swiftSettings: [
                .enableUpcomingFeature("BareSlashRegexLiterals"),
                .enableExperimentalFeature("StrictConcurrency"),
            ]
        ),
        .testTarget(
            name: "MediaKitTests",
            dependencies: ["MediaKit"]
        ),
    ]
)
