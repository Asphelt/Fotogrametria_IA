// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "PhotogrammetryTool",
    platforms: [.macOS(.v12)],
    targets: [
        .executableTarget(
            name: "PhotogrammetryTool",
            path: "Sources"
        )
    ]
)
