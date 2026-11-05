#!/usr/bin/env node
// Query the real Nunti Android bridge. No screenshots, provider calls or recording.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const arg=(name,fallback)=>process.argv.find(v=>v.startsWith(`--${name}=`))?.slice(name.length+3)??fallback;
const commandName=arg('command','snapshot');
const allowed=new Set(['snapshot','refresh','requestRoute','requestTrip','changeRouteOption','reroute','overview','foreground','cancelRoute']);
assert(allowed.has(commandName),'Unsupported navigation command');
const serial=arg('serial','emulator-5554');
assert(/^emulator-\d+$/.test(serial),'Emulator serial required');
const port=Number(arg('port','9224'));
assert(Number.isInteger(port)&&port>=1024&&port<=65535,'Invalid local debug port');
const waitMs=Number(arg('wait-ms','3000'));
assert(Number.isFinite(waitMs)&&waitMs>=0&&waitMs<=15000,'Invalid wait');
const payloadText=arg('payload','{}');
assert(payloadText.length<=16384,'Navigation payload too large');
const payload=JSON.parse(payloadText);
assert(payload&&typeof payload==='object'&&!Array.isArray(payload),'Object payload required');
const returnAfterHandoff=process.argv.includes('--return-to-nunti');
const adb=path.join(root,'.local/pm-tools/sdk/platform-tools/adb');
let launcherReturns=0;
const returnToNunti=()=>{const user=execFileSync(adb,['-s',serial,'shell','am','get-current-user'],{encoding:'utf8',timeout:5000}).trim();assert(/^\d+$/.test(user),'Android user unavailable');execFileSync(adb,['-s',serial,'shell','am','start','-W','--user',user,'-a','android.intent.action.MAIN','-c','android.intent.category.LAUNCHER','-f','0x10200000','-n','ai.nunti.avatar.demo/ai.nunti.app.MainActivity'],{stdio:'pipe',timeout:10000});launcherReturns++;};
const pid=execFileSync(adb,['-s',serial,'shell','pidof','ai.nunti.avatar.demo'],{encoding:'utf8',timeout:5000}).trim();
assert(/^\d+$/.test(pid),'Nunti Android process is not running');
execFileSync(adb,['-s',serial,'forward',`tcp:${port}`,`localabstract:webview_devtools_remote_${pid}`],{stdio:'pipe',timeout:5000});
const targets=await(await fetch(`http://127.0.0.1:${port}/json/list`,{signal:AbortSignal.timeout(5000)})).json();
const target=targets.find(v=>v.type==='page'&&v.url.startsWith('http://127.0.0.1:8768'));
assert(target,'Nunti WebView debug target not found');
const socket=new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve,reject)=>{const timer=setTimeout(()=>{socket.close();reject(new Error('WebView connection timeout'));},5000);socket.onopen=()=>{clearTimeout(timer);resolve();};socket.onerror=()=>{clearTimeout(timer);reject(new Error('WebView connection failed'));};});
let id=0;
const pending=new Map();
socket.onmessage=e=>{const v=JSON.parse(e.data);if(v.id){const item=pending.get(v.id);pending.delete(v.id);if(v.error)item?.reject(new Error('CDP command failed'));else item?.resolve(v.result);}};
const call=(method,params={})=>new Promise((resolve,reject)=>{const n=++id;pending.set(n,{resolve,reject});socket.send(JSON.stringify({id:n,method,params}));});
const evaluate=async expression=>{const v=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(v.exceptionDetails)throw new Error('Native bridge evaluation failed');return v.result?.value;};
const snapshot=async()=>{const text=await evaluate('window.NuntiNative?.getNavigationSnapshot?.()');assert(typeof text==='string'&&text.length<=1048576,'Navigation snapshot unavailable');return JSON.parse(text);};
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const deadline=setTimeout(()=>{for(const p of pending.values())p.reject(new Error('Native bridge deadline'));socket.close();},35000);
try{
  await call('Runtime.enable');
  let before=await snapshot();
  if(before.status==='GATE_BLOCKED'&&returnAfterHandoff){returnToNunti();await pause(600);before=await snapshot();}
  let ack=null,after=before,callbackObserved=false;
  const callbacks=value=>(value.events??[]).filter(event=>Number(event.sequence)>Number(before.sequence??0)&&typeof event.type==='string'&&event.type.startsWith('on'));
  const expectedCallbacks={refresh:['onCurrentLocationInfo'],requestRoute:['onRoutingCompleted','onRouteStarted'],requestTrip:['onTripInfo'],changeRouteOption:['onRouteOptionChanged'],reroute:['onReRouteEnded'],cancelRoute:['onRouteCancelled','onRouteEnded']}[commandName];
  if(commandName!=='snapshot'){
    const text=await evaluate(`window.NuntiNative.navigationCommand(${JSON.stringify(commandName)},${JSON.stringify(JSON.stringify(payload))})`);
    ack=typeof text==='string'?JSON.parse(text):text;
    const end=Date.now()+waitMs;
    while(Date.now()<end){await pause(150);after=await snapshot();if(after.status==='GATE_BLOCKED'&&returnAfterHandoff&&launcherReturns===0){returnToNunti();await pause(600);after=await snapshot();}const events=callbacks(after);callbackObserved=expectedCallbacks?events.some(event=>expectedCallbacks.includes(event.type)):events.length>0;if(callbackObserved)break;}
  }
  const artifact=await evaluate('window.nuntiTest?.getArtifact?.()??null');
  const result={status:commandName==='snapshot'?'NATIVE_SNAPSHOT_READ':ack?.accepted===false?'NATIVE_COMMAND_REJECTED':callbackObserved?'NATIVE_COMMAND_CALLBACK_OBSERVED':'NATIVE_COMMAND_SENT_CALLBACK_UNVERIFIED',command:commandName,ack,callbackObserved,observedCallbackTypes:callbacks(after).map(event=>event.type),launcherReturns,sdkSessionPreserved:before.sessionId===after.sessionId,snapshot:after,artifact,source:'ACTUAL_ANDROID_NATIVE_BRIDGE',paidApiCalls:0,videoRecorded:false,speakerRecorded:false};
  const output=arg('output',null);
  if(output){const file=path.resolve(root,output);assert(file.startsWith(root+path.sep),'Output must stay in workspace');await fs.mkdir(path.dirname(file),{recursive:true});await fs.writeFile(file,JSON.stringify(result,null,2)+'\n',{flag:'wx',mode:0o600});}
  console.log(JSON.stringify(result));
}finally{clearTimeout(deadline);socket.close();}
