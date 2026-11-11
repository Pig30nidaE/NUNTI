import Foundation
import AVFoundation
import CoreVideo

// Inspect every recorded frame. The fixed teal CTA must survive every blink and gesture.
let args=CommandLine.arguments
let asset=AVURLAsset(url:URL(fileURLWithPath:args[1]))
let reader=try AVAssetReader(asset:asset)
let track=asset.tracks(withMediaType:.video)[0]
let output=AVAssetReaderTrackOutput(track:track,outputSettings:[kCVPixelBufferPixelFormatTypeKey as String:kCVPixelFormatType_32BGRA])
reader.add(output);reader.startReading()
var count=0
var missing:[Double]=[]
while let sample=output.copyNextSampleBuffer() {
 guard let image=CMSampleBufferGetImageBuffer(sample) else {continue}
 CVPixelBufferLockBaseAddress(image,.readOnly)
 let stride=CVPixelBufferGetBytesPerRow(image)
 let bytes=CVPixelBufferGetBaseAddress(image)!.assumingMemoryBound(to:UInt8.self)
 var teal=0;var total=0
 for y in Swift.stride(from:1200,to:1240,by:4) {for x in Swift.stride(from:2200,to:2440,by:4){
  let i=y*stride+x*4;let b=Int(bytes[i]),g=Int(bytes[i+1]),r=Int(bytes[i+2])
  if(g>r+20 && b>r+20){teal+=1};total+=1
 }}
 if(Double(teal)/Double(total)<0.5){missing.append(CMTimeGetSeconds(CMSampleBufferGetPresentationTimeStamp(sample)))}
 count+=1;CVPixelBufferUnlockBaseAddress(image,.readOnly)
}
let result:[String:Any]=["frames":count,"missingUiFrames":missing.count,"missingAtSeconds":missing,"decoderCompleted":reader.status == .completed,"roi":[2200,1200,2440,1240]]
let data=try JSONSerialization.data(withJSONObject:result,options:[.prettyPrinted,.sortedKeys])
try data.write(to:URL(fileURLWithPath:args[2]));print(String(data:data,encoding:.utf8)!)
