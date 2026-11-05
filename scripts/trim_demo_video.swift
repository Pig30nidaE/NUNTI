#!/usr/bin/env swift
// Usage: swift scripts/trim_demo_video.swift VIDEO START_SECONDS END_SECONDS OUTPUT_MP4
// macOS AVFoundation only. A new silent video file; original input is never overwritten.
import AVFoundation
import CoreMedia
import CryptoKit
import Foundation

enum TrimFailure: String, Error {
    case usage = "USAGE_VIDEO_START_SECONDS_END_SECONDS_OUTPUT_MP4"
    case input = "INPUT_VIDEO_NOT_FOUND"
    case range = "INVALID_SECOND_RANGE"
    case outside = "REQUESTED_SECONDS_EXCEED_VIDEO_DURATION"
    case output = "OUTPUT_MUST_BE_A_NEW_MP4_FILE"
    case track = "EXPECTED_ONE_SOURCE_VIDEO_TRACK"
    case composition = "VIDEO_COMPOSITION_UNAVAILABLE"
    case export = "PASSTHROUGH_MP4_EXPORT_UNAVAILABLE"
    case verification = "OUTPUT_DURATION_RESOLUTION_OR_TRACK_VERIFICATION_FAILED"
    case sourceChanged = "SOURCE_VIDEO_CHANGED_DURING_EXPORT"
}

func fileHash(_ url: URL) throws -> String {
    SHA256.hash(data: try Data(contentsOf: url, options: .mappedIfSafe))
        .map { String(format: "%02x", $0) }.joined()
}

func trim(_ args: [String]) async throws -> [String: Any] {
    guard args.count == 4, let start = Double(args[1]), let end = Double(args[2]) else { throw TrimFailure.usage }
    guard start.isFinite, end.isFinite, start >= 0, end > start else { throw TrimFailure.range }
    let source = URL(fileURLWithPath: args[0]).standardizedFileURL
    let destination = URL(fileURLWithPath: args[3]).standardizedFileURL
    let fm = FileManager.default
    guard fm.fileExists(atPath: source.path) else { throw TrimFailure.input }
    guard source != destination, destination.pathExtension.lowercased() == "mp4",
          !fm.fileExists(atPath: destination.path) else { throw TrimFailure.output }
    let originalHash = try fileHash(source)
    let asset = AVURLAsset(url: source)
    let tracks = try await asset.loadTracks(withMediaType: .video)
    guard tracks.count == 1 else { throw TrimFailure.track }
    let video = tracks[0], sourceRange = try await video.load(.timeRange)
    let sourceDuration = CMTimeGetSeconds(sourceRange.duration)
    guard sourceDuration.isFinite, end <= sourceDuration else { throw TrimFailure.outside }
    let sourceSize = try await video.load(.naturalSize), transform = try await video.load(.preferredTransform)
    let sourceFormats = try await video.load(.formatDescriptions)
    let composition = AVMutableComposition()
    guard let copiedVideo = composition.addMutableTrack(withMediaType: .video,
                        preferredTrackID: kCMPersistentTrackID_Invalid) else { throw TrimFailure.composition }
    let selectedRange = CMTimeRange(start: CMTimeAdd(sourceRange.start, CMTime(seconds: start, preferredTimescale: 600_000)),
                                   duration: CMTime(seconds: end - start, preferredTimescale: 600_000))
    try copiedVideo.insertTimeRange(selectedRange, of: video, at: .zero)
    copiedVideo.preferredTransform = transform
    guard let exporter = AVAssetExportSession(asset: composition, presetName: AVAssetExportPresetPassthrough),
          exporter.supportedFileTypes.contains(.mp4) else { throw TrimFailure.export }
    try fm.createDirectory(at: destination.deletingLastPathComponent(), withIntermediateDirectories: true)
    let temporary = destination.deletingLastPathComponent().appendingPathComponent(".trim-\(UUID().uuidString).mp4")
    defer { try? fm.removeItem(at: temporary) }
    try await exporter.export(to: temporary, as: .mp4)
    let finalAsset = AVURLAsset(url: temporary)
    let finalVideos = try await finalAsset.loadTracks(withMediaType: .video)
    let finalAudios = try await finalAsset.loadTracks(withMediaType: .audio)
    guard finalVideos.count == 1, finalAudios.isEmpty else { throw TrimFailure.verification }
    let durationTime = try await finalAsset.load(.duration)
    let duration = CMTimeGetSeconds(durationTime)
    let finalSize = try await finalVideos[0].load(.naturalSize)
    let finalTransform = try await finalVideos[0].load(.preferredTransform)
    let finalFormats = try await finalVideos[0].load(.formatDescriptions)
    let sourceMatrix = [transform.a, transform.b, transform.c, transform.d, transform.tx, transform.ty]
    let finalMatrix = [finalTransform.a, finalTransform.b, finalTransform.c, finalTransform.d, finalTransform.tx, finalTransform.ty]
    guard duration.isFinite, abs(duration - (end - start)) <= 0.05,
          abs(finalSize.width - sourceSize.width) < 0.01, abs(finalSize.height - sourceSize.height) < 0.01,
          zip(sourceMatrix, finalMatrix).allSatisfy({ abs($0 - $1) < 0.001 }),
          sourceFormats.first.map({ CMFormatDescriptionGetMediaSubType($0) }) == finalFormats.first.map({ CMFormatDescriptionGetMediaSubType($0) }) else {
        FileHandle.standardError.write(Data("Verification: requestedDuration=\(end-start) actualDuration=\(duration) sourceSize=\(sourceSize) finalSize=\(finalSize)\n".utf8))
        throw TrimFailure.verification
    }
    guard try fileHash(source) == originalHash else { throw TrimFailure.sourceChanged }
    try fm.moveItem(at: temporary, to: destination)
    return ["status": "SILENT_VIDEO_PASSTHROUGH_TRIM_VERIFIED", "output": destination.path,
            "sourceVideo": source.path, "sourceSha256": originalHash,
            "outputSha256": try fileHash(destination), "sourceUnchanged": true,
            "startSeconds": start, "endSeconds": end, "requestedDurationSeconds": end - start,
            "outputDurationSeconds": duration, "sourceVideoDurationSeconds": sourceDuration,
            "videoTrackCount": finalVideos.count, "audioTrackCount": finalAudios.count,
            "pixelWidth": finalSize.width, "pixelHeight": finalSize.height,
            "originalResolutionAndTransformPreserved": true, "playbackRate": 1.0,
            "exportPreset": AVAssetExportPresetPassthrough, "audioAddedOrSubstituted": false]
}

Task {
    do {
        let result = try await trim(Array(CommandLine.arguments.dropFirst()))
        let data = try JSONSerialization.data(withJSONObject: result, options: [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes])
        FileHandle.standardOutput.write(data); FileHandle.standardOutput.write(Data("\n".utf8)); exit(0)
    } catch {
        let code = (error as? TrimFailure)?.rawValue ?? "AVFOUNDATION_OR_FILE_OPERATION_FAILED"
        let result: [String: Any] = ["status": "FAILED", "error": code]
        if let data = try? JSONSerialization.data(withJSONObject: result, options: [.sortedKeys]) {
            FileHandle.standardOutput.write(data); FileHandle.standardOutput.write(Data("\n".utf8))
        }
        let native = error as NSError
        FileHandle.standardError.write(Data("\(code) [\(native.domain):\(native.code)]\n".utf8)); exit(2)
    }
}
dispatchMain()
