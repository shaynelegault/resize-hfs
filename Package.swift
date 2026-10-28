// swift-tools-version: 5.9
// SPDX-License-Identifier: MIT
import PackageDescription

let package = Package(
    name: "ResizeHFS",
    products: [
        .library(name: "ResizeCore", targets: ["ResizeCore"]),
        .executable(name: "resize-inspect", targets: ["ResizeInspect"]),
        .executable(name: "inspect-hfs-image", targets: ["HFSImageInspect"]),
        .executable(name: "inspect-gpt-header", targets: ["GPTHeaderInspect"]),
        .executable(name: "inspect-revision1-fixture", targets: ["Revision1FixtureInspect"])
    ],
    targets: [
        .target(name: "ResizeCore"),
        .executableTarget(name: "ResizeInspect", dependencies: ["ResizeCore"]),
        .executableTarget(name: "HFSImageInspect", dependencies: ["ResizeCore"]),
        .executableTarget(name: "GPTHeaderInspect", dependencies: ["ResizeCore"]),
        .executableTarget(name: "Revision1FixtureInspect", dependencies: ["ResizeCore"]),
        .testTarget(name: "ResizeCoreTests", dependencies: ["ResizeCore"])
    ]
)
