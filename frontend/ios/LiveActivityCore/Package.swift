// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "LiveActivityCore",
    products: [.library(name: "LiveActivityCore", targets: ["LiveActivityCore"])],
    targets: [
        .target(name: "LiveActivityCore"),
        .testTarget(
            name: "LiveActivityCoreTests",
            dependencies: ["LiveActivityCore"],
            resources: [.copy("Fixtures")]
        ),
    ]
)
