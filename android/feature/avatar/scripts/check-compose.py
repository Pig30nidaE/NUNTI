#!/usr/bin/env python3
"""Compile actual Compose/AAOS sources against official binaries. Not an APK/emulator test."""
import argparse, pathlib, subprocess, urllib.request, zipfile, concurrent.futures
p=argparse.ArgumentParser()
p.add_argument('--kotlinc',required=True)
p.add_argument('--android-jar',required=True)
p.add_argument('--car-jar',required=True)
p.add_argument('--cache',required=True)
a=p.parse_args()
root=pathlib.Path(__file__).resolve().parents[4]
cache=pathlib.Path(a.cache);cache.mkdir(parents=True,exist_ok=True)
version='1.8.3'
modules=[('runtime','runtime-android'),('runtime','runtime-saveable-android'),('ui','ui-android'),('ui','ui-geometry-android'),('ui','ui-graphics-android'),('ui','ui-unit-android'),('ui','ui-util-android'),('ui','ui-text-android'),('foundation','foundation-android'),('foundation','foundation-layout-android')]
def fetch(item):
 group,name=item
 target=cache/f'{name}-{version}.jar'
 if not target.exists():
  url=f'https://dl.google.com/dl/android/maven2/androidx/compose/{group}/{name}/{version}/{name}-{version}.aar'
  archive=cache/f'{name}-{version}.aar'
  urllib.request.urlretrieve(url,archive)
  with zipfile.ZipFile(archive) as z: target.write_bytes(z.read('classes.jar'))
 return target
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool: jars=list(pool.map(fetch,modules))
compiler=pathlib.Path(a.kotlinc).resolve()
plugin=compiler.parent.parent/'lib/compose-compiler-plugin.jar'
assert plugin.exists(), 'Official Kotlin distribution Compose compiler plugin required'
source=[root/'android/feature/navigation/src/main/kotlin',root/'android/feature/emotion/src/main/kotlin',root/'android/feature/avatar/src/main/kotlin',root/'android/feature/avatar/src/compose/kotlin']
cmd=[str(compiler),*[str(x) for x in source],'-jvm-target','17','-classpath',':'.join([a.android_jar,a.car_jar,*map(str,jars)]),f'-Xplugin={plugin}','-d',str(cache/'avatar-compose.jar')]
subprocess.run(cmd,check=True)
print('PASS actual Compose + AAOS Kotlin compilation:',cache/'avatar-compose.jar')
