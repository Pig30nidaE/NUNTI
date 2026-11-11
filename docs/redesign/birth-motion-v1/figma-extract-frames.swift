import Foundation
import AVFoundation
import ImageIO
import UniformTypeIdentifiers

// Local, deterministic inspection of MP4 exports. No network or model calls.
// swift -module-cache-path /private/tmp/nunti-swift-cache figma-extract-frames.swift INPUT.mp4 OUTPUT_PREFIX
let args = CommandLine.arguments
guard args.count == 3 else { fatalError("Expected input MP4 and output prefix") }
let asset = AVURLAsset(url: URL(fileURLWithPath: args[1]))
let generator = AVAssetImageGenerator(asset: asset)
generator.appliesPreferredTrackTransform = true
generator.requestedTimeToleranceBefore = .zero
generator.requestedTimeToleranceAfter = .zero
let times: [Double] = [0, 0.4, 0.8, 1.0, 1.4, 2.0, 2.2, 2.6, 3.0, 3.8, 4.0]
for time in times {
    var actual = CMTime.zero
    let image = try generator.copyCGImage(at: CMTime(seconds: time, preferredTimescale: 600), actualTime: &actual)
    let suffix = String(format: "%.1f", time)
    let output = URL(fileURLWithPath: args[2] + "-" + suffix + ".png")
    guard let destination = CGImageDestinationCreateWithURL(output as CFURL, UTType.png.identifier as CFString, 1, nil) else { fatalError("Cannot create PNG") }
    CGImageDestinationAddImage(destination, image, nil)
    guard CGImageDestinationFinalize(destination) else { fatalError("Cannot write PNG") }
    print("\(suffix)s actual=\(CMTimeGetSeconds(actual)) \(image.width)x\(image.height) \(output.lastPathComponent)")
}
print("duration=\(CMTimeGetSeconds(asset.duration))")
for track in asset.tracks(withMediaType: .video) {
    print("nominalFrameRate=\(track.nominalFrameRate) size=\(track.naturalSize)")
}
