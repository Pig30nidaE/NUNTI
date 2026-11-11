import Foundation
import AVFoundation
import AppKit

// Inspect real device recordings. This does not generate or change production artwork.
let arguments=CommandLine.arguments
guard arguments.count>=4 else { fatalError("video output-directory seconds...") }
let asset=AVURLAsset(url:URL(fileURLWithPath:arguments[1]))
let generator=AVAssetImageGenerator(asset:asset)
generator.appliesPreferredTrackTransform=true
generator.requestedTimeToleranceBefore=CMTime.zero
generator.requestedTimeToleranceAfter=CMTime.zero
let out=URL(fileURLWithPath:arguments[2],isDirectory:true)
try FileManager.default.createDirectory(at:out,withIntermediateDirectories:true)
var faces:[(String,CGImage)]=[]
for value in arguments.dropFirst(3) {
    let seconds=Double(value)!
    let cg=try generator.copyCGImage(at:CMTime(seconds:seconds,preferredTimescale:600),actualTime:nil)
    let representation=NSBitmapImageRep(cgImage:cg)
    try representation.representation(using:.png,properties:[:])!.write(to:out.appendingPathComponent("frame-\(value).png"))
    if let crop=cg.cropping(to:CGRect(x:1140,y:400,width:350,height:350)) {faces.append((value,crop))}
}
let strip=NSImage(size:NSSize(width:faces.count*200,height:230))
strip.lockFocus()
NSColor.white.setFill();NSRect(x:0,y:0,width:faces.count*200,height:230).fill()
for (index,pair) in faces.enumerated() {
 NSImage(cgImage:pair.1,size:.zero).draw(in:NSRect(x:index*200,y:30,width:200,height:200))
 (pair.0+"s" as NSString).draw(at:NSPoint(x:index*200+80,y:5),withAttributes:[.font:NSFont.systemFont(ofSize:16),.foregroundColor:NSColor.black])
}
strip.unlockFocus()
try NSBitmapImageRep(data:strip.tiffRepresentation!)!.representation(using:.png,properties:[:])!.write(to:out.appendingPathComponent("face-contact.png"))
print("Saved \(arguments.count-3) device video frames")
