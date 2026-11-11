#!/usr/bin/env python3
"""Bounded public-emulator NMEA probe. No recording, app restart or private API."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import subprocess
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
ADB = ROOT / '.local/pm-tools/sdk/platform-tools/adb'
NAV = 'ai.umos.maps.android.navigation.app'

class GpsController:
    """Authenticated localhost control; restore the exact seven-field protobuf afterward."""
    def __init__(self, folder):
        import grpc
        from google.protobuf.empty_pb2 import Empty
        from google.protobuf.json_format import MessageToDict
        from record_emulator_audio import find_discovery
        from verify_navigation_integration import grpc_bindings
        _, props, target = find_discovery('emulator-5554')
        if props.get('grpc.server_cert') or props.get('grpc.tls'):
            raise RuntimeError('TLS_CONFIG_UNSUPPORTED_NO_PLAINTEXT_FALLBACK')
        bindings = folder / 'bindings'; bindings.mkdir()
        self.pb, _ = grpc_bindings(bindings)
        self.channel = grpc.insecure_channel(target)
        grpc.channel_ready_future(self.channel).result(timeout=5)
        self.metadata = (('authorization', 'Bearer ' + props['grpc.token']),)
        self.empty = Empty
        self.get = self.channel.unary_unary('/android.emulation.control.EmulatorController/getGps',
            request_serializer=Empty.SerializeToString,response_deserializer=self.pb.GpsState.FromString)
        self.set = self.channel.unary_unary('/android.emulation.control.EmulatorController/setGps',
            request_serializer=self.pb.GpsState.SerializeToString,response_deserializer=Empty.FromString)
        self.before = self.get(Empty(),timeout=5,metadata=self.metadata)
        (folder/'controller-before.json').write_text(json.dumps(MessageToDict(self.before, preserving_proto_field_name=True)))
    def disable_passive(self):
        # setGps itself emits host-generated NMEA. Call it once, before the raw-only
        # observation window. Some public emulator versions ignore passiveUpdate.
        if not self.before.passiveUpdate:
            return
        value = self.pb.GpsState(); value.CopyFrom(self.before)
        value.passiveUpdate = False
        self.set(value,timeout=5,metadata=self.metadata)
        if self.get(self.empty(),timeout=5,metadata=self.metadata).passiveUpdate:
            raise RuntimeError('PASSIVE_UPDATE_DISABLE_NOT_SUPPORTED: automatic GPS remains enabled')
    def restore(self):
        try:
            self.set(self.before,timeout=5,metadata=self.metadata)
            return self.get(self.empty(),timeout=5,metadata=self.metadata) == self.before
        finally: self.channel.close()

def adb(*args):
    return subprocess.run([str(ADB), '-s', 'emulator-5554', *map(str, args)], capture_output=True,
                          text=True, timeout=5, check=True).stdout

def sentence(body):
    checksum = 0
    for char in body:
        checksum ^= ord(char)
    return f'${body}*{checksum:02X}'

def coordinate(value, latitude):
    degree = int(abs(value)); minutes = (abs(value) - degree) * 60
    return f'{degree:0{2 if latitude else 3}d}{minutes:09.6f}', ('N' if value >= 0 else 'S') if latitude else ('E' if value >= 0 else 'W')

def sentences(lat, lon, altitude, speed_mps, bearing):
    # API 34 Goldfish uses an integer HHMMSS sscanf field and requires magnetic variation.
    now = datetime.now(timezone.utc); clock = now.strftime('%H%M%S')
    la, ns = coordinate(lat, True); lo, ew = coordinate(lon, False)
    return [sentence(f'GPGGA,{clock},{la},{ns},{lo},{ew},1,08,0.9,{altitude:.1f},M,0.0,M,,'),
            sentence(f'GPRMC,{clock},A,{la},{ns},{lo},{ew},{speed_mps / 0.514444:.3f},{bearing:.3f},{now:%d%m%y},0.0,W')]

def distance(a, b):
    lat = math.radians((a[1] + b[1]) / 2)
    return math.hypot((a[0]-b[0])*111320*math.cos(lat), (a[1]-b[1])*111320)

def route_point(points, meters):
    for a, b in zip(points, points[1:]):
        length = distance(a, b)
        if meters <= length:
            t = meters / length if length else 0
            bearing = math.degrees(math.atan2((b[0]-a[0])*math.cos(math.radians(a[1])), b[1]-a[1])) % 360
            return [a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t], bearing, 5.0
        meters -= length
    return points[-1], 0.0, 0.0

def console(path, values=None):
    url = 'http://127.0.0.1:8088' + path
    if values is not None: url += '?' + urllib.parse.urlencode(values)
    with urllib.request.urlopen(urllib.request.Request(url, method='PUT' if values is not None else 'GET'), timeout=4) as response:
        return json.load(response)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--with-fix', action='store_true', help='Also send the public geo fix input')
    parser.add_argument('--with-console', action='store_true', help='Synchronize vehicle speed and restore Console values')
    parser.add_argument('--passive-off', action='store_true', help='Use authenticated getGps/setGps to disable automatic malformed NMEA')
    args = parser.parse_args()
    if not args.run:
        print('Use --run for a 20-second NMEA probe; optional --with-fix --with-console. No video.')
        return
    folder = ROOT / '.local/integration-2026-11-05' / ('nmea-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    folder.mkdir(parents=True)
    if args.passive_off and args.with_fix: parser.error('Use --passive-off or --with-fix, not both')
    controller = None
    raw = adb('shell', 'dumpsys', 'location'); (folder / 'before-location.txt').write_text(raw)
    match = re.search(r'last location=Location\[gps ([-\d.]+),([-\d.]+).*?alt=([-\d.]+).*?vel=([-\d.]+).*?bear=([-\d.]+)', raw)
    if args.passive_off:
        controller = GpsController(folder)
        lat, lon, altitude, velocity, bearing = (controller.before.latitude, controller.before.longitude,
            controller.before.altitude, controller.before.speed, controller.before.bearing)
    else:
        if not match: raise RuntimeError('Original GPS position/speed/bearing cannot be read')
        lat, lon, altitude, velocity, bearing = map(float, match.groups())
    pid = adb('shell', 'pidof', NAV).strip(); assert pid.isdigit()
    points = json.loads((ROOT / '.local/navigation-integration/live/native-plan.json').read_text())['geometry']['coordinates'][:10]
    before_console = console('/vehicle/state') if args.with_console else None
    report = {'input': vars(args), 'beforeGps': dict(latitude=lat, longitude=lon, altitude=altitude, velocity=velocity, bearing=bearing),
              'frames': [], 'nativeMoved': False, 'videoRecorded': False,
              'controllerSatelliteAndPassiveSettings': 'RESTORE_PENDING' if args.passive_off else 'NOT_VERIFIED' if args.with_fix else 'NOT_EXPLICITLY_CHANGED'}
    started = float(adb('shell', 'date', '+%s').strip())
    try:
        if controller:
            controller.disable_passive()
            disabled_at = float(adb('shell', 'date', '+%s').strip())
            time.sleep(3)
            quiet_log = adb('logcat','-d','-v','epoch','-t','4000','--pid='+pid)
            (folder/'passive-disable-observation.log').write_text(quiet_log)
            errors = []
            for line in quiet_log.splitlines():
                stamp = re.match(r'\s*(\d+\.\d+)',line)
                if stamp and float(stamp[1]) >= disabled_at + 1 and 'Invalid NMEA message' in line:
                    errors.append(line)
            report['automaticNmeaErrorsAfterDisable'] = errors
            if errors: raise RuntimeError('AUTOMATIC_NMEA_STILL_PRESENT: raw-only probe was not started')
            report['passiveDisableReadbackConfirmed'] = True
            started = float(adb('shell', 'date', '+%s').strip())
        if args.with_console: console('/vehicle/gear', {'gear':'Drive'})
        epoch = time.monotonic()
        for index in range(20):
            if time.monotonic() - epoch > 35: raise TimeoutError('GPS probe exceeded its live-input time bound')
            point, heading, speed = route_point(points, index * 5)
            if args.with_console: console('/vehicle/controls', {'speed':round(speed*3.6), 'accelerator':0, 'brake':0, 'steering':0})
            if args.with_fix:
                result = adb('emu','geo','fix', point[0],point[1],altitude,8,speed/0.514444)
                if 'KO' in result: raise RuntimeError(result)
            frames = sentences(point[1],point[0],altitude,speed,heading)
            for frame in frames:
                result = adb('emu','geo','nmea',frame)
                if 'KO' in result: raise RuntimeError(result)
            report['frames'].append({'point':point,'bearing':heading,'speedMps':speed,'sentences':frames})
            if index % 5 == 4: print('sent',index+1,'frames',flush=True)
            time.sleep(max(0, epoch + index + 1 - time.monotonic()))
        native = adb('logcat','-d','-v','epoch','-t','4000','--pid='+pid)
        (folder/'native-after.log').write_text(native)
        locations = []
        for line in native.splitlines():
            stamp = re.match(r'\s*(\d+\.\d+)',line)
            location = re.search(r'\borg\(([-\d.]+),([-\d.]+)',line)
            if stamp and float(stamp[1]) >= started and location: locations.append(list(map(float,location.groups())))
        report['nativeLocations'] = locations
        nearby = [p for p in locations if distance(points[0], p) < 200]
        displacement = max((distance(a,b) for a in nearby for b in nearby), default=0)
        report['nativeDisplacementMeters'] = displacement
        report['nativeMoved'] = displacement > 5
        (folder/'after-location.txt').write_text(adb('shell','dumpsys','location'))
    except Exception as error:
        report['failure'] = str(error)
        raise
    finally:
        restore_errors = []
        if controller:
            try: report['fullControllerStateRestored'] = controller.restore()
            except Exception as error:
                report['fullControllerStateRestored'] = False
                restore_errors.append('controller: '+str(error))
            report['controllerSatelliteAndPassiveSettings'] = 'RESTORED_EXACT_PROTO' if report['fullControllerStateRestored'] else 'RESTORE_FAILED'
        if args.with_fix:
            try: report['restoreFixResponse'] = adb('emu','geo','fix',lon,lat,altitude).strip()
            except Exception as error: restore_errors.append('geo fix: '+str(error))
        for frame in sentences(lat,lon,altitude,velocity,bearing):
            try: adb('emu','geo','nmea',frame)
            except Exception as error: restore_errors.append('NMEA restore: '+str(error))
        if before_console:
            c = before_console['controls']; gear = before_console['gear']['actual']['value']
            requests = [('/vehicle/controls',{'speed':0,'accelerator':0,'brake':0,'steering':c['steering_deg']}),
                ('/vehicle/gear',{'gear':gear}),
                ('/vehicle/controls',{'speed':c['speed_kph'],'accelerator':c['accelerator_pct'],'brake':c['brake_pct'],'steering':c['steering_deg']})]
            for endpoint, values in requests:
                try: console(endpoint,values)
                except Exception as error: restore_errors.append('Console '+endpoint+': '+str(error))
            try:
                observed = console('/vehicle/state')
                report['consoleRestored'] = observed['gear']['actual']['value'] == gear and all(observed['controls'][k] == c[k] for k in ('speed_kph','accelerator_pct','brake_pct','steering_deg'))
            except Exception as error:
                report['consoleRestored'] = False; restore_errors.append('Console readback: '+str(error))
        time.sleep(2)
        try:
            restored = adb('shell','dumpsys','location'); (folder/'restored-location.txt').write_text(restored)
            check = re.search(r'last location=Location\[gps ([-\d.]+),([-\d.]+)',restored)
            report['gpsPositionRestored'] = bool(check and distance([lon,lat],[float(check[2]),float(check[1])]) < 2)
        except Exception as error:
            report['gpsPositionRestored'] = False; restore_errors.append('GPS readback: '+str(error))
        report['restoreErrors'] = restore_errors
        (folder/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({'nativeMoved':report['nativeMoved'],'gpsPositionRestored':report['gpsPositionRestored'],'report':str(folder/'report.json')}))

if __name__ == '__main__': main()
