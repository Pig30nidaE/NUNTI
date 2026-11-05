#!/usr/bin/env swift
// Local AVFoundation muxer. Copy compressed video samples, encode the supplied WAV as AAC.
// Usage: swift scripts/mux_emulator_demo.swift VIDEO WAV OFFSET_SECONDS OUTPUT_MP4
// Set CLANG_MODULE_CACHE_PATH and SWIFT_MODULECACHE_PATH to a workspace cache before invoking Swift.
import AVFoundation
import CoreMedia
import CryptoKit
import Foundation

enum MuxFailure: String, Error {
    case usage = "USAGE_VIDEO_WAV_OFFSET_SECONDS_OUTPUT_MP4"
    case input = "INVALID_INPUT_OR_OFFSET"
    case outputExists = "OUTPUT_ALREADY_EXISTS"
    case tracks = "EXPECTED_ONE_VIDEO_AND_ONE_WAV_AUDIO_TRACK"
    case sourceAudio = "SOURCE_VIDEO_ALREADY_HAS_AUDIO"
    case overlap = "AUDIO_DOES_NOT_OVERLAP_VIDEO"
    case format = "UNSUPPORTED_SOURCE_FORMAT"
    case reader = "MEDIA_READER_FAILED"
    case writer = "MEDIA_WRITER_FAILED"
    case timing = "SAMPLE_TIMING_COPY_FAILED"
    case timeout = "MUX_TIMEOUT"
    case videoChanged = "COMPRESSED_VIDEO_SAMPLES_CHANGED"
    case verification = "OUTPUT_TRACK_OR_DURATION_VERIFICATION_FAILED"
}

func writerFailure(_ writer: AVAssetWriter, _ stage: String) -> MuxFailure {
    let detail = writer.error.map { "\(($0 as NSError).domain):\(($0 as NSError).code) \($0.localizedDescription)" } ?? "no framework error"
    FileHandle.standardError.write(Data("Writer \(stage): \(detail)\n".utf8))
    return .writer
}

func seconds(_ value: CMTime) throws -> Double {
    let result = CMTimeGetSeconds(value)
    guard result.isFinite else { throw MuxFailure.format }
    return result
}

func fileHash(_ url: URL) throws -> String {
    let file = try FileHandle(forReadingFrom: url)
    defer { try? file.close() }
    var digest = SHA256()
    while let block = try file.read(upToCount: 1_048_576), !block.isEmpty {
        digest.update(data: block)
    }
    return digest.finalize().map { String(format: "%02x", $0) }.joined()
}

func shifted(_ buffer: CMSampleBuffer, by offset: CMTime) throws -> CMSampleBuffer {
    var needed = 0
    let queryStatus = CMSampleBufferGetSampleTimingInfoArray(buffer, entryCount: 0, arrayToFill: nil,
                                               entriesNeededOut: &needed)
    guard needed > 0 else {
        let type = CMSampleBufferGetFormatDescription(buffer).map { CMFormatDescriptionGetMediaType($0) } ?? 0
        FileHandle.standardError.write(Data("Timing query status=\(queryStatus) needed=\(needed) type=\(type) samples=\(CMSampleBufferGetNumSamples(buffer)) pts=\(CMTimeGetSeconds(CMSampleBufferGetPresentationTimeStamp(buffer))) duration=\(CMTimeGetSeconds(CMSampleBufferGetDuration(buffer)))\n".utf8))
        throw MuxFailure.timing
    }
    var values = [CMSampleTimingInfo](repeating: CMSampleTimingInfo(duration: .invalid,
                            presentationTimeStamp: .invalid, decodeTimeStamp: .invalid), count: needed)
    guard CMSampleBufferGetSampleTimingInfoArray(buffer, entryCount: needed, arrayToFill: &values,
                                               entriesNeededOut: &needed) == noErr else { throw MuxFailure.timing }
    for index in values.indices {
        if values[index].presentationTimeStamp.isValid {
            values[index].presentationTimeStamp = CMTimeAdd(values[index].presentationTimeStamp, offset)
        }
        if values[index].decodeTimeStamp.isValid {
            values[index].decodeTimeStamp = CMTimeAdd(values[index].decodeTimeStamp, offset)
        }
    }
    var copy: CMSampleBuffer?
    guard CMSampleBufferCreateCopyWithNewTiming(allocator: kCFAllocatorDefault, sampleBuffer: buffer,
            sampleTimingEntryCount: values.count, sampleTimingArray: &values,
            sampleBufferOut: &copy) == noErr, let copy else { throw MuxFailure.timing }
    return copy
}

struct VideoFingerprint {
    let sha256: String
    let timestamps: [Double]
}

func firstSampleTime(_ asset: AVAsset, track: AVAssetTrack) throws -> Double {
    let reader = try AVAssetReader(asset: asset)
    let output = AVAssetReaderTrackOutput(track: track, outputSettings: nil)
    guard reader.canAdd(output) else { throw MuxFailure.reader }
    reader.add(output)
    guard reader.startReading() else { throw MuxFailure.reader }
    while let sample = output.copyNextSampleBuffer() {
        if CMSampleBufferGetNumSamples(sample) == 0 { continue }
        let timestamp = try seconds(CMSampleBufferGetPresentationTimeStamp(sample))
        reader.cancelReading()
        return timestamp
    }
    throw MuxFailure.reader
}

let envelopeBinSeconds = 0.005

func pcmEnvelope(_ asset: AVAsset, track: AVAssetTrack, range: CMTimeRange,
                 sampleRate: Double, channels: Int) throws -> [Double] {
    let duration = try seconds(range.duration), start = try seconds(range.start)
    let bins = Int(ceil(duration / envelopeBinSeconds))
    guard bins > 0 else { throw MuxFailure.verification }
    var sums = [Double](repeating: 0, count: bins), counts = [Int](repeating: 0, count: bins)
    let reader = try AVAssetReader(asset: asset)
    let output = AVAssetReaderTrackOutput(track: track, outputSettings: [
        AVFormatIDKey: kAudioFormatLinearPCM, AVLinearPCMBitDepthKey: 16,
        AVLinearPCMIsFloatKey: false, AVLinearPCMIsBigEndianKey: false,
        AVLinearPCMIsNonInterleaved: false, AVSampleRateKey: sampleRate, AVNumberOfChannelsKey: channels,
    ])
    guard reader.canAdd(output) else { throw MuxFailure.reader }
    reader.add(output); reader.timeRange = range
    guard reader.startReading() else { throw MuxFailure.reader }
    while let sample = output.copyNextSampleBuffer() {
        let frames = CMSampleBufferGetNumSamples(sample)
        if frames == 0 { continue }
        guard let block = CMSampleBufferGetDataBuffer(sample) else { throw MuxFailure.format }
        let length = CMBlockBufferGetDataLength(block)
        guard length >= frames * channels * 2 else { throw MuxFailure.format }
        var bytes = Data(count: length)
        let status = bytes.withUnsafeMutableBytes { memory in
            CMBlockBufferCopyDataBytes(block, atOffset: 0, dataLength: length, destination: memory.baseAddress!)
        }
        guard status == noErr else { throw MuxFailure.reader }
        let stamp = try seconds(CMSampleBufferGetPresentationTimeStamp(sample))
        bytes.withUnsafeBytes { memory in
            for frame in 0..<frames {
                let bin = Int(floor((stamp + Double(frame) / sampleRate - start) / envelopeBinSeconds))
                if bin < 0 || bin >= bins { continue }
                var energy = 0.0
                for channel in 0..<channels {
                    let value = Double(memory.loadUnaligned(fromByteOffset: (frame * channels + channel) * 2,
                                                            as: Int16.self).littleEndian) / 32768
                    energy += value * value
                }
                sums[bin] += energy / Double(channels); counts[bin] += 1
            }
        }
    }
    guard reader.status == .completed else { throw MuxFailure.reader }
    return zip(sums, counts).map { $1 == 0 ? 0 : sqrt($0 / Double($1)) }
}

func correlatedOffset(source: [Double], output: [Double], expected: Double) throws -> (offset: Double, correlation: Double) {
    let expectedBin = Int((expected / envelopeBinSeconds).rounded())
    var bestOffset = 0, bestCorrelation = -Double.infinity
    // Search a narrow technical timing window, not the whole recording for another voice.
    for shift in max(0, expectedBin - 20)...min(output.count - 1, expectedBin + 20) {
        let count = min(source.count, output.count - shift)
        if count < 40 { continue }
        let sourceMean = source.prefix(count).reduce(0, +) / Double(count)
        let outputMean = output[shift..<(shift + count)].reduce(0, +) / Double(count)
        var numerator = 0.0, sourcePower = 0.0, outputPower = 0.0
        for index in 0..<count {
            let a = source[index] - sourceMean, b = output[index + shift] - outputMean
            numerator += a * b; sourcePower += a * a; outputPower += b * b
        }
        if sourcePower <= 1e-12 || outputPower <= 1e-12 { continue }
        let correlation = numerator / sqrt(sourcePower * outputPower)
        if correlation > bestCorrelation { bestCorrelation = correlation; bestOffset = shift }
    }
    guard bestCorrelation.isFinite else { throw MuxFailure.verification }
    return (Double(bestOffset) * envelopeBinSeconds, bestCorrelation)
}

func videoFingerprint(_ asset: AVAsset, track: AVAssetTrack, start: CMTime) throws -> VideoFingerprint {
    let reader = try AVAssetReader(asset: asset)
    let output = AVAssetReaderTrackOutput(track: track, outputSettings: nil)
    output.alwaysCopiesSampleData = false
    guard reader.canAdd(output) else { throw MuxFailure.reader }
    reader.add(output)
    guard reader.startReading() else { throw MuxFailure.reader }
    var digest = SHA256()
    var timestamps = [Double]()
    while let sample = output.copyNextSampleBuffer() {
        if CMSampleBufferGetNumSamples(sample) == 0 { continue }
        guard let block = CMSampleBufferGetDataBuffer(sample) else { throw MuxFailure.format }
        let byteCount = CMBlockBufferGetDataLength(block)
        var data = Data(count: byteCount)
        let status = data.withUnsafeMutableBytes { memory in
            CMBlockBufferCopyDataBytes(block, atOffset: 0, dataLength: byteCount, destination: memory.baseAddress!)
        }
        guard status == kCMBlockBufferNoErr else { throw MuxFailure.reader }
        digest.update(data: data)
        timestamps.append(try seconds(CMTimeSubtract(CMSampleBufferGetPresentationTimeStamp(sample), start)))
    }
    guard reader.status == .completed, !timestamps.isEmpty else { throw MuxFailure.reader }
    return VideoFingerprint(sha256: digest.finalize().map { String(format: "%02x", $0) }.joined(), timestamps: timestamps)
}

func mux(_ arguments: [String]) async throws -> [String: Any] {
    guard arguments.count == 4, let offsetSeconds = Double(arguments[2]), offsetSeconds.isFinite else { throw MuxFailure.usage }
    let videoURL = URL(fileURLWithPath: arguments[0]).standardizedFileURL
    let wavURL = URL(fileURLWithPath: arguments[1]).standardizedFileURL
    let outputURL = URL(fileURLWithPath: arguments[3]).standardizedFileURL
    let fm = FileManager.default
    guard fm.fileExists(atPath: videoURL.path), fm.fileExists(atPath: wavURL.path),
          videoURL != outputURL, wavURL != outputURL, outputURL.pathExtension.lowercased() == "mp4" else { throw MuxFailure.input }
    guard !fm.fileExists(atPath: outputURL.path) else { throw MuxFailure.outputExists }
    try fm.createDirectory(at: outputURL.deletingLastPathComponent(), withIntermediateDirectories: true)
    let temporary = outputURL.deletingLastPathComponent().appendingPathComponent(".mux-\(UUID().uuidString).mp4")
    defer { try? fm.removeItem(at: temporary) }

    let videoAsset = AVURLAsset(url: videoURL), audioAsset = AVURLAsset(url: wavURL)
    let videos = try await videoAsset.loadTracks(withMediaType: .video)
    let sourceAudios = try await videoAsset.loadTracks(withMediaType: .audio)
    let audios = try await audioAsset.loadTracks(withMediaType: .audio)
    guard videos.count == 1, audios.count == 1 else { throw MuxFailure.tracks }
    guard sourceAudios.isEmpty else { throw MuxFailure.sourceAudio }
    let video = videos[0], audio = audios[0]
    let videoRange = try await video.load(.timeRange), audioRange = try await audio.load(.timeRange)
    let videoDuration = try seconds(videoRange.duration), audioDuration = try seconds(audioRange.duration)
    let leadingAudioTrim = max(0, -offsetSeconds), outputAudioStart = max(0, offsetSeconds)
    let usedAudioDuration = min(audioDuration - leadingAudioTrim, videoDuration - outputAudioStart)
    guard videoDuration > 0, audioDuration > 0, usedAudioDuration > 0 else { throw MuxFailure.overlap }
    let videoFormats = try await video.load(.formatDescriptions), audioFormats = try await audio.load(.formatDescriptions)
    guard let videoFormat = videoFormats.first, let audioFormat = audioFormats.first,
          let basic = CMAudioFormatDescriptionGetStreamBasicDescription(audioFormat) else { throw MuxFailure.format }
    let sampleRate = basic.pointee.mSampleRate, channels = Int(basic.pointee.mChannelsPerFrame)
    guard sampleRate.isFinite, sampleRate > 0, channels > 0, channels <= 8 else { throw MuxFailure.format }

    let videoReader = try AVAssetReader(asset: videoAsset), audioReader = try AVAssetReader(asset: audioAsset)
    let videoOutput = AVAssetReaderTrackOutput(track: video, outputSettings: nil)
    videoOutput.alwaysCopiesSampleData = false
    let audioOutput = AVAssetReaderTrackOutput(track: audio, outputSettings: [
        AVFormatIDKey: kAudioFormatLinearPCM, AVLinearPCMBitDepthKey: 16,
        AVLinearPCMIsFloatKey: false, AVLinearPCMIsBigEndianKey: false, AVLinearPCMIsNonInterleaved: false,
    ])
    guard videoReader.canAdd(videoOutput), audioReader.canAdd(audioOutput) else { throw MuxFailure.reader }
    videoReader.add(videoOutput); audioReader.add(audioOutput)
    let audioSourceStart = CMTimeAdd(audioRange.start, CMTime(seconds: leadingAudioTrim, preferredTimescale: 600_000))
    audioReader.timeRange = CMTimeRange(start: audioSourceStart,
                                      duration: CMTime(seconds: usedAudioDuration, preferredTimescale: 600_000))
    let writer = try AVAssetWriter(outputURL: temporary, fileType: .mp4)
    let videoInput = AVAssetWriterInput(mediaType: .video, outputSettings: nil, sourceFormatHint: videoFormat)
    videoInput.expectsMediaDataInRealTime = false
    videoInput.transform = try await video.load(.preferredTransform)
    videoInput.mediaTimeScale = try await video.load(.naturalTimeScale)
    let audioInput = AVAssetWriterInput(mediaType: .audio, outputSettings: [
        AVFormatIDKey: kAudioFormatMPEG4AAC, AVSampleRateKey: sampleRate,
        AVNumberOfChannelsKey: channels, AVEncoderBitRateKey: channels == 1 ? 64_000 : 128_000,
    ])
    audioInput.expectsMediaDataInRealTime = false
    guard writer.canAdd(videoInput), writer.canAdd(audioInput) else { throw writerFailure(writer, "cannot add inputs") }
    writer.add(videoInput); writer.add(audioInput)
    guard writer.startWriting() else { throw writerFailure(writer, "start") }
    guard videoReader.startReading(), audioReader.startReading() else { throw MuxFailure.reader }
    writer.startSession(atSourceTime: .zero)
    let videoShift = CMTimeMultiplyByFloat64(videoRange.start, multiplier: -1)
    let audioShift = CMTimeSubtract(CMTime(seconds: outputAudioStart, preferredTimescale: 600_000), audioSourceStart)
    var videoDone = false, audioDone = false, videoSamples = 0, audioSamples = 0
    let began = ProcessInfo.processInfo.systemUptime
    while !videoDone || !audioDone {
        if writer.status == .failed { throw writerFailure(writer, "pump") }
        if ProcessInfo.processInfo.systemUptime - began > 900 { throw MuxFailure.timeout }
        var advanced = false
        if !videoDone && videoInput.isReadyForMoreMediaData {
            if let sample = videoOutput.copyNextSampleBuffer() {
                if CMSampleBufferGetNumSamples(sample) > 0 {
                    guard videoInput.append(try shifted(sample, by: videoShift)) else { throw writerFailure(writer, "video append") }
                    videoSamples += 1
                }
            } else {
                guard videoReader.status == .completed else { throw MuxFailure.reader }
                videoInput.markAsFinished(); videoDone = true
            }
            advanced = true
        }
        if !audioDone && audioInput.isReadyForMoreMediaData {
            if let sample = audioOutput.copyNextSampleBuffer() {
                if CMSampleBufferGetNumSamples(sample) > 0 {
                    let shiftedSample = try shifted(sample, by: audioShift)
                    guard audioInput.append(shiftedSample) else { throw writerFailure(writer, "audio append") }
                    audioSamples += CMSampleBufferGetNumSamples(sample)
                }
            } else {
                guard audioReader.status == .completed else { throw MuxFailure.reader }
                audioInput.markAsFinished(); audioDone = true
            }
            advanced = true
        }
        if !advanced { usleep(1_000) }
    }
    writer.endSession(atSourceTime: videoRange.duration)
    await writer.finishWriting()
    guard writer.status == .completed, videoSamples > 0, audioSamples > 0 else { throw writerFailure(writer, "finish") }

    let delivered = AVURLAsset(url: temporary)
    let finalVideos = try await delivered.loadTracks(withMediaType: .video)
    let finalAudios = try await delivered.loadTracks(withMediaType: .audio)
    guard finalVideos.count == 1, finalAudios.count == 1 else { throw MuxFailure.verification }
    let finalVideoRange = try await finalVideos[0].load(.timeRange)
    let finalAudioRange = try await finalAudios[0].load(.timeRange)
    let finalTime = try await delivered.load(.duration)
    let finalDuration = try seconds(finalTime)
    let sourceFingerprint = try videoFingerprint(videoAsset, track: video, start: videoRange.start)
    let finalFingerprint = try videoFingerprint(delivered, track: finalVideos[0], start: finalVideoRange.start)
    guard sourceFingerprint.sha256 == finalFingerprint.sha256,
          sourceFingerprint.timestamps.count == finalFingerprint.timestamps.count else { throw MuxFailure.videoChanged }
    let maximumTimestampDifference = zip(sourceFingerprint.timestamps, finalFingerprint.timestamps).map { abs($0 - $1) }.max() ?? 0
    let finalVideoDuration = try seconds(finalVideoRange.duration), finalAudioStart = try seconds(finalAudioRange.start)
    // AAC can encode a leading silent gap and expose a t=0 packet even when input starts later.
    // Verify the supplied waveform's envelope at its intended position instead of trusting track start.
    let firstAudioSample = try firstSampleTime(delivered, track: finalAudios[0])
    let sourceEnvelope = try pcmEnvelope(audioAsset, track: audio, range: CMTimeRange(start: audioSourceStart,
        duration: CMTime(seconds: usedAudioDuration, preferredTimescale: 600_000)), sampleRate: sampleRate, channels: channels)
    let outputEnvelope = try pcmEnvelope(delivered, track: finalAudios[0], range: CMTimeRange(start: .zero,
        duration: CMTime(seconds: videoDuration, preferredTimescale: 600_000)), sampleRate: sampleRate, channels: channels)
    let alignment = try correlatedOffset(source: sourceEnvelope, output: outputEnvelope, expected: outputAudioStart)
    let audioStartError = abs(alignment.offset - outputAudioStart)
    guard maximumTimestampDifference <= 0.002, abs(finalVideoDuration - videoDuration) <= 0.1,
          abs(finalDuration - videoDuration) <= 0.1,
          audioStartError <= 0.025, alignment.correlation >= 0.90 else {
        FileHandle.standardError.write(Data("Verification: ptsDifference=\(maximumTimestampDifference) videoDuration=\(videoDuration) finalVideoDuration=\(finalVideoDuration) finalDuration=\(finalDuration) expectedAudioStart=\(outputAudioStart) trackStart=\(finalAudioStart) firstAudioSample=\(firstAudioSample) measuredAudioOffset=\(alignment.offset) envelopeNcc=\(alignment.correlation) audioError=\(audioStartError)\n".utf8))
        throw MuxFailure.verification
    }
    try fm.moveItem(at: temporary, to: outputURL)
    return [
        "status": "VIDEO_PASSTHROUGH_AND_CAPTURED_WAV_MUX_VERIFIED", "output": outputURL.path,
        "sourceVideoSha256": try fileHash(videoURL), "sourceWavSha256": try fileHash(wavURL),
        "outputSha256": try fileHash(outputURL), "videoTrackCount": 1, "audioTrackCount": 1,
        "sourceVideoDurationSeconds": videoDuration, "outputDurationSeconds": finalDuration,
        "sourceWavDurationSeconds": audioDuration, "requestedAudioOffsetSeconds": offsetSeconds,
        "audioSourceLeadingTrimSeconds": leadingAudioTrim, "audioUsedSeconds": usedAudioDuration,
        "audioSourceTailTrimSeconds": max(0, audioDuration - leadingAudioTrim - usedAudioDuration),
        "audioTrackStartSeconds": finalAudioStart, "audioTrackDurationSeconds": try seconds(finalAudioRange.duration),
        "audioFirstSamplePresentationSeconds": firstAudioSample,
        "audioMeasuredOffsetSeconds": alignment.offset, "audioEnvelopeCorrelation": alignment.correlation,
        "audioOffsetVerification": "LOCAL_5MS_PCM_RMS_ENVELOPE_CORRELATION",
        "audioStartErrorSeconds": audioStartError, "audioCodec": "AAC", "audioSampleRateHz": sampleRate,
        "audioChannels": channels, "audioPitchOrSpeedChanged": false, "audioSourceSubstituted": false,
        "compressedVideoSampleSha256": sourceFingerprint.sha256, "compressedVideoSamplesUnchanged": true,
        "videoSampleCount": sourceFingerprint.timestamps.count, "maximumVideoTimestampDifferenceSeconds": maximumTimestampDifference,
    ]
}

Task {
    do {
        let result = try await mux(Array(CommandLine.arguments.dropFirst()))
        let data = try JSONSerialization.data(withJSONObject: result, options: [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes])
        FileHandle.standardOutput.write(data); FileHandle.standardOutput.write(Data("\n".utf8))
        exit(0)
    } catch {
        let code = (error as? MuxFailure)?.rawValue ?? "AVFOUNDATION_OR_FILE_OPERATION_FAILED"
        let result: [String: Any] = ["status": "FAILED", "error": code]
        if let data = try? JSONSerialization.data(withJSONObject: result, options: [.sortedKeys]) {
            FileHandle.standardOutput.write(data); FileHandle.standardOutput.write(Data("\n".utf8))
        }
        let native = error as NSError
        FileHandle.standardError.write(Data("\(code) [\(native.domain):\(native.code)]\n".utf8))
        exit(2)
    }
}
dispatchMain()
