// Extract actual recorded frames for visual QA, without changing the source video.
// Usage: swift scripts/extract_demo_frames.swift VIDEO OUTPUT_DIR SECONDS...
import AVFoundation
import CryptoKit
import Foundation
import ImageIO
import UniformTypeIdentifiers

let arguments = Array(CommandLine.arguments.dropFirst())
guard arguments.count >= 3 else { fatalError("Usage: VIDEO OUTPUT_DIR SECONDS...") }
let source = URL(fileURLWithPath: arguments[0])
let directory = URL(fileURLWithPath: arguments[1])
let stamps = arguments.dropFirst(2).compactMap { Double($0) }
guard stamps.count == arguments.count - 2, stamps.allSatisfy({ $0.isFinite && $0 >= 0 }) else { fatalError("Invalid frame time") }
guard !FileManager.default.fileExists(atPath: directory.path) else { fatalError("Choose a new output directory") }
try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
let asset = AVURLAsset(url: source)
let generator = AVAssetImageGenerator(asset: asset)
generator.appliesPreferredTrackTransform = true
generator.requestedTimeToleranceBefore = .zero
generator.requestedTimeToleranceAfter = .zero
var frames = [[String: Any]]()
for (index, time) in stamps.enumerated() {
    var actual = CMTime.zero
    let image = try generator.copyCGImage(at: CMTime(seconds: time, preferredTimescale: 60000), actualTime: &actual)
    let file = directory.appendingPathComponent(String(format: "frame-%02d.png", index))
    guard let destination = CGImageDestinationCreateWithURL(file as CFURL, UTType.png.identifier as CFString, 1, nil) else {
        fatalError("Cannot create PNG destination")
    }
    CGImageDestinationAddImage(destination, image, nil)
    guard CGImageDestinationFinalize(destination) else { fatalError("Cannot write PNG") }
    frames.append(["file": file.path, "requestedSeconds": time, "actualSeconds": CMTimeGetSeconds(actual),
                   "width": image.width, "height": image.height])
}
let digest = SHA256.hash(data: try Data(contentsOf: source)).map { String(format: "%02x", $0) }.joined()
let report: [String: Any] = ["status": "ACTUAL_VIDEO_FRAMES_EXTRACTED", "sourceVideo": source.path,
                            "sourceSha256": digest, "frames": frames]
let json = try JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys])
try json.write(to: directory.appendingPathComponent("index.json"))
FileHandle.standardOutput.write(json)
