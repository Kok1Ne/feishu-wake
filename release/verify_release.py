"""Validate the signed Release through its real UI on a fresh cloud API 30 emulator."""
import datetime,hashlib,json,os,re,subprocess,time,urllib.request
from pathlib import Path
import xml.etree.ElementTree as ET
if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':
    raise SystemExit('Release verification is cloud-only')
ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'reports/release-device'
REPORT.mkdir(parents=True,exist_ok=True)
APK=ROOT/'app/build/outputs/apk/release/app-release.apk'
PACKAGE='dev.feishuwake'
TARGET='com.ss.android.lark'
checks={}
host=(REPORT/'adb-host.log').open('w',encoding='utf-8')
def adb(*args,timeout=60,check=True):
    p=subprocess.run(['adb','-s','emulator-5554',*args],capture_output=True,text=True,
                     encoding='utf-8',errors='replace',timeout=timeout)
    host.write(' '.join(args)+'\n'+p.stdout+p.stderr+'\n');host.flush()
    if check and p.returncode: raise RuntimeError('ADB failed: '+str(args))
    return p.stdout
def record(name,ok):
    checks[name]='PASS' if ok else 'FAIL'
    print(name+': '+checks[name],flush=True)
    if not ok: raise RuntimeError(name)
def snapshot(name):
    out={}
    for service in ['power','window policy','activity activities','alarm']:
        out[service]=adb('shell','dumpsys',*service.split())
        (REPORT/(name+'-'+service.replace(' ','-')+'.txt')).write_text(out[service],encoding='utf-8')
    return out
def locked(text):
    tail=text.split('KeyguardServiceDelegate',1)[-1]
    m=re.search(r'(?m)^\s*showing=(true|false)\s*$',tail)
    return None if not m else m.group(1)=='true'
def front(text):
    return any(TARGET+'/' in s for s in text.splitlines() if 'mResumedActivity' in s or 'topResumedActivity' in s)
def ui_node(text,scroll=False):
    for attempt in range(9 if scroll else 1):
        adb('shell','uiautomator','dump','/sdcard/release-ui.xml')
        raw=adb('shell','cat','/sdcard/release-ui.xml')
        (REPORT/('ui-'+str(time.time_ns())+'.xml')).write_text(raw,encoding='utf-8')
        root=ET.fromstring(raw[raw.index('<?xml'):])
        matches=[n for n in root.iter('node') if n.get('package')==PACKAGE and text in n.get('text','')
                 and n.get('enabled')=='true']
        for node in matches:
            b=list(map(int,re.findall(r'\d+',node.get('bounds',''))))
            if len(b)==4 and b[2]>b[0] and b[3]>b[1]:
                return node,b
        if scroll: adb('shell','input','swipe','540','1500','540','600','300')
    raise RuntimeError('Release UI control not found: '+text)
def tap(text,scroll=False):
    node,(x1,y1,x2,y2)=ui_node(text,scroll)
    adb('shell','input','tap',str((x1+x2)//2),str((y1+y2)//2))
def open_main():
    adb('shell','input','keyevent','224')
    adb('shell','wm','dismiss-keyguard')
    deadline=time.monotonic()+12
    stable=None
    while time.monotonic()<deadline:
        policy=adb('shell','dumpsys','window','policy')
        if locked(policy) is False and 'screenState=SCREEN_STATE_ON' in policy:
            stable=stable or time.monotonic()
            if time.monotonic()-stable>=1.5: break
        else: stable=None
        time.sleep(.2)
    else: raise RuntimeError('Release UI setup did not reach a stable unlocked state')
    result=adb('shell','am','start','-W','-n',PACKAGE+'/dev.feishuwake.MainActivity')
    if 'Status: ok' not in result: raise RuntimeError('Release did not start')
def tap_resource(resource):
    for attempt in range(10):
        adb('shell','uiautomator','dump','/sdcard/release-ui.xml')
        raw=adb('shell','cat','/sdcard/release-ui.xml')
        root=ET.fromstring(raw[raw.index('<?xml'):])
        for node in root.iter('node'):
            if node.get('resource-id')==resource and node.get('enabled')=='true':
                b=list(map(int,re.findall(r'\d+',node.get('bounds',''))))
                if len(b)==4 and b[2]>b[0] and b[3]>b[1]:
                    adb('shell','input','tap',str((b[0]+b[2])//2),str((b[1]+b[3])//2))
                    return
        adb('shell','input','swipe','540','1500','540','600','300')
    raise RuntimeError('Release UI resource not found: '+resource)
def capture(name):
    adb('shell','uiautomator','dump','/sdcard/release-ui.xml')
    (REPORT/(name+'.xml')).write_text(adb('shell','cat','/sdcard/release-ui.xml'),encoding='utf-8')
    raw=subprocess.run(['adb','-s','emulator-5554','exec-out','screencap','-p'],capture_output=True,check=True,timeout=30).stdout
    if not raw.startswith(b'\x89PNG\r\n\x1a\n'): raise RuntimeError('Screenshot is not PNG')
    (REPORT/(name+'.png')).write_bytes(raw)
def parse_events(raw):
    result=[]
    for line in raw.splitlines():
        if 'FeishuWake' in line and '{' in line:
            try: result.append(json.loads(line[line.index('{'):]))
            except ValueError: pass
    return result

try:
    record('api30_boot',adb('shell','getprop','ro.build.version.sdk').strip()=='30' and
           adb('shell','getprop','sys.boot_completed').strip()=='1')
    record('install_official_feishu','Success' in adb('install','-r',str(Path(os.environ['RUNNER_TEMP'])/'official-feishu.apk'),timeout=240))
    adb('shell','locksettings','set-disabled','false')
    adb('shell','settings','put','secure','lock_screen_lock_after_timeout','0')
    adb('shell','settings','put','global','stay_on_while_plugged_in','0')
    adb('shell','settings','put','system','screen_off_timeout','30000')
    # Verify a real 1.0.0 -> 1.0.1 update with the published APK and fixed certificate.
    previous=Path(os.environ['RUNNER_TEMP'])/'FeishuWake-1.0.0.apk'
    url='https://github.com/Kok1Ne/feishu-wake/releases/download/v1.0.0/FeishuWake-1.0.0.apk'
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'FeishuWake-cloud-validation'}),timeout=90) as response:
        previous.write_bytes(response.read())
    record('previous_release_sha256',hashlib.sha256(previous.read_bytes()).hexdigest()=='f9d7b8e6f52a09a51c21ca74b0a09159ddd7975f759c69426b3e9641fac3f759')
    record('install_previous_release','Success' in adb('install','-r',str(previous),timeout=180))
    open_main()
    node,_=ui_node('自动化总开关')
    if node.get('checked')!='true': tap('自动化总开关')
    before_update=adb('shell','dumpsys','alarm')
    record('previous_config_enabled',PACKAGE in before_update and '*walarm*:scheduled' in before_update)
    adb('logcat','-b','all','-c')
    record('install_release','Success' in adb('install','-r',str(APK),timeout=180))
    end=time.monotonic()+30
    while time.monotonic()<end:
        updated=adb('logcat','-d','-v','brief','-s','FeishuWake:I')
        if 'MY_PACKAGE_REPLACED' in updated: break
        time.sleep(1)
    (REPORT/'update-logcat.txt').write_text(updated,encoding='utf-8')
    record('release_update_receiver','MY_PACKAGE_REPLACED' in updated)
    after_update=snapshot('after-update')
    record('release_schedule_survives_update',PACKAGE in after_update['alarm'] and '*walarm*:scheduled' in after_update['alarm'])
    open_main()
    node,_=ui_node('自动化总开关')
    record('release_config_survives_update',node.get('checked')=='true')
    tap('自动化总开关')
    capture('ui-schedule')
    record('release_ui_launch',True)
    adb('logcat','-b','all','-c')
    tap('立即测试',scroll=True)
    adb('shell','input','keyevent','3')
    adb('shell','input','keyevent','223')
    until=time.monotonic()+7
    while time.monotonic()<until:
        if locked(adb('shell','dumpsys','window','policy')) is True: break
        time.sleep(.25)
    initial=snapshot('before')
    record('initial_asleep','mWakefulness=Asleep' in initial['power'])
    record('initial_swipe_keyguard',locked(initial['window policy']) is True)
    record('initial_feishu_not_foreground',not front(initial['activity activities']))
    deadline=time.monotonic()+50
    while time.monotonic()<deadline and not front(adb('shell','dumpsys','activity','activities')): time.sleep(1)
    time.sleep(5)
    after=snapshot('after')
    record('release_awake','mWakefulness=Awake' in after['power'])
    record('release_keyguard_dismissed',locked(after['window policy']) is False)
    record('release_real_feishu_foreground_stable',front(after['activity activities']))
    raw=adb('logcat','-d','-v','brief','-s','FeishuWake:I')
    (REPORT/'flow-logcat.txt').write_text(raw,encoding='utf-8')
    rows=[]
    for line in raw.splitlines():
        if 'FeishuWake' in line and '{' in line:
            try: rows.append(json.loads(line[line.index('{'):]))
            except ValueError: pass
    ids=[r['run'] for r in rows if r.get('stage')=='trigger' and r.get('status')=='OK']
    record('release_single_alarm',len(ids)==1)
    stages=[(r.get('stage'),r.get('status')) for r in rows if r.get('run')==ids[0]]
    record('release_unlock_before_launch',('keyguard','OK') in stages and ('launch','REQUESTED') in stages and
           stages.index(('keyguard','OK'))<stages.index(('launch','REQUESTED')))
    # The signed release's compatibility route is exercised through its consent UI.
    # With an unlocked screen the ordinary full-screen intent may stay heads-up only.
    open_main()
    tap_resource(PACKAGE+':id/navigation_logs')
    capture('ui-logs')
    tap_resource(PACKAGE+':id/navigation_settings')
    capture('ui-settings')
    adb('shell','appops','set',PACKAGE,'SYSTEM_ALERT_WINDOW','allow')
    tap_resource(PACKAGE+':id/compatibility_toggle')
    tap_resource('android:id/button1')
    node,_=ui_node('启用兼容唤醒')
    record('release_compatibility_ui_opt_in',node.get('checked')=='true')
    tap_resource(PACKAGE+':id/navigation_schedule')
    adb('logcat','-b','all','-c')
    tap('立即测试',scroll=True)
    adb('shell','input','keyevent','3')
    start=snapshot('compat-before')
    record('release_compatibility_initial_unlocked',locked(start['window policy']) is False)
    deadline=time.monotonic()+65
    while time.monotonic()<deadline and not front(adb('shell','dumpsys','activity','activities')): time.sleep(1)
    time.sleep(5)
    after=snapshot('compat-after')
    raw=adb('logcat','-d','-v','brief','-s','FeishuWake:I')
    (REPORT/'compat-logcat.txt').write_text(raw,encoding='utf-8')
    rows=parse_events(raw)
    record('release_compatibility_requested',sum(r.get('stage')=='compatibility' and r.get('status')=='REQUESTED' for r in rows)==1)
    record('release_compatibility_foreground_stable',front(after['activity activities']))
    record('release_compatibility_awake_unlocked','mWakefulness=Awake' in after['power'] and locked(after['window policy']) is False)
    stages=[(r.get('stage'),r.get('status')) for r in rows]
    record('release_compatibility_unlock_before_launch',('keyguard','OK') in stages and ('launch','REQUESTED') in stages and stages.index(('keyguard','OK'))<stages.index(('launch','REQUESTED')))
    open_main()
    tap_resource(PACKAGE+':id/navigation_settings')
    tap_resource(PACKAGE+':id/compatibility_toggle')
    adb('shell','appops','set',PACKAGE,'SYSTEM_ALERT_WINDOW','default')

except Exception as error:
    checks['blocked']='FAIL'
    print(type(error).__name__+': '+str(error),flush=True)
finally:
    (REPORT/'logcat.txt').write_text(adb('logcat','-d','-v','threadtime',check=False),encoding='utf-8')
    host.close()
    (REPORT/'results.json').write_text(json.dumps({'checks':checks,'apk_sha256':hashlib.sha256(APK.read_bytes()).hexdigest(),
        'source_commit':os.environ['GITHUB_SHA'],'note':'API 30 emulator; physical-device policies and attendance unverified.'},indent=2),encoding='utf-8')
    if not checks or any(v!='PASS' for v in checks.values()): raise SystemExit(1)
