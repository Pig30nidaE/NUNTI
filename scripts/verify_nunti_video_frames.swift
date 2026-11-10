// Extract real screenrecord frames with macOS' built-in decoder. No downloads.
import Foundation
import AVFoundation
import AppKit

guard CommandLine.arguments.count == 3 else { fatalError("video.mp4 output-directory") }
let input = URL(fileURLWithPath: CommandLine.arguments[1])
let output = URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true)
try FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)
let asset = AVURLAsset(url: input)
let generator = AVAssetImageGenerator(asset: asset)
generator.appliesPreferredTrackTransform = true
generator.requestedTimeToleranceBefore = .zero
generator.requestedTimeToleranceAfter = .zero
var frames: [[String: Any]] = []
for seconds in [0.0, 1.0, 2.0, 3.0, 4.0, 5.0] {
    var actual = CMTime.zero
    let image = try generator.copyCGImage(at: CMTime(seconds: seconds, preferredTimescale: 600), actualTime: &actual)
    let name = String(format: "video-%04d.png", Int(seconds * 1000))
    let bitmap = NSBitmapImageRep(cgImage: image)
    guard let png = bitmap.representation(using: .png, properties: [:]) else { fatalError("PNG encoding failed") }
    try png.write(to: output.appendingPathComponent(name))
    frames.append(["requestedSeconds": seconds, "actualSeconds": actual.seconds,
                   "width": image.width, "height": image.height, "file": name])
}
let tracks = asset.tracks(withMediaType: .video).map { track -> [String: Any] in
    ["nominalFrameRate": track.nominalFrameRate, "estimatedDataRate": track.estimatedDataRate,
     "width": track.naturalSize.width, "height": track.naturalSize.height]
}
let metadata: [String: Any] = ["source": input.path, "decoder": "macOS AVFoundation",
                              "durationSeconds": asset.duration.seconds, "videoTracks": tracks, "frames": frames]
try JSONSerialization.data(withJSONObject: metadata, options: [.prettyPrinted, .sortedKeys])
    .write(to: output.appendingPathComponent("decoded-frames.json"))
print("Decoded \(frames.count) actual production screenrecord frames")
