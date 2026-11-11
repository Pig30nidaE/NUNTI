#!/usr/bin/env python3
"""Replay a short saved route through emulator GPS, restoring all GPS fields afterward."""
import json
import math
import sys
import tempfile
import time
from pathlib import Path
import grpc
from google.protobuf.empty_pb2 import Empty
import verify_navigation_integration as core
from record_emulator_audio import find_discovery

plan=json.loads(Path(sys.argv[1]).read_text())
out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
points=core.coordinates_from_plan(plan);core.verify_plan(plan,points)
_,properties,target=find_discovery('emulator-5554')
metadata=(('authorization','Bearer '+properties['grpc.token']),)
with tempfile.TemporaryDirectory(dir=out,prefix='proto-') as temp:
 pb,_=core.grpc_bindings(Path(temp))
 channel=grpc.insecure_channel(target)
 get=channel.unary_unary('/android.emulation.control.EmulatorController/getGps',request_serializer=Empty.SerializeToString,response_deserializer=pb.GpsState.FromString)
 put=channel.unary_unary('/android.emulation.control.EmulatorController/setGps',request_serializer=pb.GpsState.SerializeToString,response_deserializer=Empty.FromString)
 baseline=get(Empty(),timeout=5,metadata=metadata)
 fields=tuple(pb.GpsState.DESCRIPTOR.fields_by_name)
 (out/'gps-before.json').write_text(json.dumps({k:getattr(baseline,k) for k in fields}))
 distance=[0.0]
 for a,b in zip(points,points[1:]):distance.append(distance[-1]+core.point_distance_m(a,b))
 requested=[]
 try:
  for step in range(36):
   traveled=min(step*9.0,distance[-1])
   index=next((i for i in range(1,len(points)) if distance[i]>=traveled),len(points)-1)
   fraction=(traveled-distance[index-1])/max(.001,distance[index]-distance[index-1])
   lon,lat=[a+(b-a)*fraction for a,b in zip(points[index-1],points[index])]
   state=pb.GpsState();state.CopyFrom(baseline)
   state.longitude=lon;state.latitude=lat;state.speed=18;state.passiveUpdate=False;state.satellites=max(4,baseline.satellites)
   put(state,timeout=5,metadata=metadata);requested.append([lon,lat]);time.sleep(1)
 finally:
  put(baseline,timeout=5,metadata=metadata)
  restored=get(Empty(),timeout=5,metadata=metadata)
  result={'source':'saved API route replay through emulator GPS','requestedLonLat':requested,
    'gpsRestored':all(getattr(restored,k)==getattr(baseline,k) for k in fields)}
  (out/'gps-replay.json').write_text(json.dumps(result,indent=2));channel.close()
  print(json.dumps({'steps':len(requested),'gpsRestored':result['gpsRestored']}),flush=True)
