"""Host-side P0/P1 check. Requires a booted API 30 emulator; never runs on a USB phone.

This script does not authorize Release: mock-target passes are not Feishu passes.
"""
import argparse, datetime, json, pathlib, re, subprocess, time, sys
p=argparse.ArgumentParser()
p.add_argument('--adb',required=True); p.add_argument('--port',default='5037'); p.add_argument('--serial',required=True)
p.add_argument('--target',choices=['mock','feishu'],default='mock')
p.add_argument('--report-dir',type=pathlib.Path)
args=p.parse_args()
if not re.fullmatch(r'emulator-\d+',args.serial): raise SystemExit('Use an emulator serial, not a real phone.')
ROOT=pathlib.Path(__file__).resolve().parents[1]; REPORT=args.report_dir or ROOT/'reports'; REPORT.mkdir(parents=True,exist_ok=True)
log=(REPORT/'android-host.log').open('w',encoding='utf-8')
checks={}; package='dev.feishuwake.debug'
def adb(*cmd,timeout=30,check=True):
    proc=subprocess.run([args.adb,'-P',args.port,'-s',args.serial,*cmd],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
    log.write(datetime.datetime.now(datetime.timezone.utc).isoformat()+' '+' '.join(cmd)+'\n'+proc.stdout+proc.stderr+'\n'); log.flush()
    if check and proc.returncode: raise RuntimeError('ADB command failed: '+str(cmd))
    return proc.stdout
def control(op): adb('shell','am','broadcast','-n',package+'/dev.feishuwake.DebugControlReceiver','--es','op',op)
def wait_target(target,timeout=40):
    until=time.monotonic()+timeout
    while time.monotonic()<until:
        activities=adb('shell','dumpsys','activity','activities')
        if any(target in line for line in activities.splitlines() if 'mResumedActivity' in line or 'topResumedActivity' in line): return True
        time.sleep(1)
    return False
try:
    if adb('shell','getprop','sys.boot_completed').strip()!='1': raise RuntimeError('Android has not completed boot')
    if adb('shell','getprop','ro.build.version.sdk').strip()!='30': raise RuntimeError('Expected Android API 30')
    checks['api30_boot']='PASS'
    for path in [ROOT/'app/build/outputs/apk/debug/app-debug.apk',ROOT/'app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk']:
        adb('install','-r',str(path),timeout=120)
    if args.target=='mock': adb('install','-r',str(ROOT/'testtarget/build/outputs/apk/debug/testtarget-debug.apk'),timeout=120)
    adb('shell','am','start','-W','-n',package+'/dev.feishuwake.MainActivity')
    checks['install_launch']='PASS'
    control(args.target)
    target='dev.feishuwake.testtarget' if args.target=='mock' else 'com.ss.android.lark'
    if not adb('shell','pm','path',target,check=False).strip(): raise RuntimeError('Requested target app is not installed')
    for route in ('b','a'):
        control('stop'); control('test_'+route)
        adb('shell','input','keyevent','3')
        adb('shell','input','keyevent','223')
        adb('shell','dumpsys','power')
        # No instrumentation is active: preserve true background Activity launch restrictions.
        checks['screen_off_route_'+route]='PASS' if wait_target(target) else 'FAIL'
        adb('shell','dumpsys','window','policy')
        adb('shell','dumpsys','power')
        adb('logcat','-d','-s','FeishuWake:I','ActivityTaskManager:I','AndroidRuntime:E')
    control('stop')
    result=adb('shell','am','instrument','-w','-r','-e','class','dev.feishuwake.CoreInstrumentedTest#configRoundTripAndCancellation',package+'.test/androidx.test.runner.AndroidJUnitRunner',timeout=120)
    checks['instrumentation_config_cancel']='PASS' if 'OK (1 test)' in result and 'FAILURES' not in result else 'FAIL'
except Exception as e:
    checks['blocked']=type(e).__name__+': '+str(e)
finally:
    log.close()
    (REPORT/'android-host-results.json').write_text(json.dumps({'target':args.target,'checks':checks,'release_eligible':False,'note':'P0/P1 partial tests only. A fixture is not Feishu; full matrix and independent lock-state assertions are still required.'},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(checks,ensure_ascii=False))
    if 'blocked' in checks or 'FAIL' in checks.values(): sys.exit(1)
