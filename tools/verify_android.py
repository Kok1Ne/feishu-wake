"""Cloud-only API 30 probe with independent screen/keyguard/foreground evidence.
No instrumentation is active during alarm delivery. The fixture is not Feishu.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument('--adb', required=True)
parser.add_argument('--port', default='5037')
parser.add_argument('--serial', required=True)
parser.add_argument('--target', choices=['mock', 'feishu'], default='mock')
parser.add_argument('--report-dir', type=Path)
parser.add_argument('--routes', default='b', choices=['b','a','ba'])
parser.add_argument('--extended', action='store_true')
args = parser.parse_args()
if not re.fullmatch(r'emulator-\d+', args.serial):
    raise SystemExit('An emulator serial is required; never run this probe on a phone.')
ROOT = Path(__file__).resolve().parents[1]
REPORT = args.report_dir or ROOT / 'reports'
REPORT.mkdir(parents=True, exist_ok=True)
log = (REPORT / 'android-host.log').open('w', encoding='utf-8')
checks = {}
PACKAGE = 'dev.feishuwake.debug'
CASE_START = None
TARGET = 'dev.feishuwake.testtarget' if args.target == 'mock' else 'com.ss.android.lark'

def adb(*command, timeout=40, check=True):
    result = subprocess.run([args.adb, '-P', args.port, '-s', args.serial, *command],
                            capture_output=True, text=True, encoding='utf-8',
                            errors='replace', timeout=timeout)
    log.write(datetime.datetime.now(datetime.timezone.utc).isoformat() + ' ' +
              ' '.join(command) + '\n' + result.stdout + result.stderr + '\n')
    log.flush()
    if check and result.returncode:
        raise RuntimeError('ADB failed: ' + repr(command) + ': ' + result.stderr[-1000:])
    return result.stdout

def control(op):
    return adb('shell', 'am', 'broadcast', '-n', PACKAGE + '/dev.feishuwake.DebugControlReceiver',
               '--es', 'op', op)

def record(name, condition, detail=''):
    checks[name] = {'status': 'PASS' if condition else 'FAIL', 'detail': detail}
    print(name + ': ' + checks[name]['status'] + (' ' + detail if detail else ''), flush=True)
    return condition

def snapshot(name):
    values = {}
    for service in ('power', 'window policy', 'activity activities', 'alarm'):
        text = adb('shell', 'dumpsys', *service.split())
        (REPORT / (name + '-' + service.replace(' ', '-') + '.txt')).write_text(text, encoding='utf-8')
        values[service] = text
    return values

def screen(power):
    match = re.search(r'mWakefulness=(\w+)', power)
    return match.group(1) if match else 'UNKNOWN'

def keyguard(policy):
    # Restrict "showing" to KeyguardServiceDelegate: unrelated window fields are not evidence.
    section = policy.split('KeyguardServiceDelegate', 1)[-1] if 'KeyguardServiceDelegate' in policy else ''
    match = re.search(r'(?m)^\s*showing=(true|false)\s*$', section)
    return match.group(1) == 'true' if match else None

def foreground(text):
    return any(TARGET + '/' in line for line in text.splitlines()
               if 'mResumedActivity' in line or 'topResumedActivity' in line)

def wait_foreground(timeout=40):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if foreground(adb('shell', 'dumpsys', 'activity', 'activities')):
            return True
        time.sleep(1)
    return False

def events(name):
    raw = adb('logcat', '-d', '-v', 'brief', '-s', 'FeishuWake:I', 'ActivityTaskManager:I', 'AndroidRuntime:E')
    (REPORT / (name + '-logcat.txt')).write_text(raw, encoding='utf-8')
    rows = []
    for line in raw.splitlines():
        if 'FeishuWake' not in line or '{' not in line:
            continue
        try:
            row = json.loads(line[line.index('{'):])
            if CASE_START is not None and datetime.datetime.fromisoformat(row['at'].replace('Z','+00:00')) < CASE_START:
                continue
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
        except ValueError:
            pass
    return rows

def wait_locked_asleep(timeout=7):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        policy=adb('shell','dumpsys','window','policy')
        power=adb('shell','dumpsys','power')
        if keyguard(policy) is True and screen(power)=='Asleep':
            return
        time.sleep(0.25)

def prepare_unlocked():
    """Settle the user's setup interaction before scheduling/sleeping; never run during a trial."""
    adb('shell','input','keyevent','224')
    adb('shell','wm','dismiss-keyguard',check=False)
    adb('shell','input','keyevent','3')
    deadline=time.monotonic()+12
    stable=None
    while time.monotonic()<deadline:
        policy=adb('shell','dumpsys','window','policy')
        power=adb('shell','dumpsys','power')
        ready=(keyguard(policy) is False and screen(power)=='Awake' and
               'screenState=SCREEN_STATE_ON' in policy and 'interactiveState=INTERACTIVE_STATE_AWAKE' in policy)
        if ready:
            stable=stable or time.monotonic()
            if time.monotonic()-stable>=1.5:
                return
        else:
            stable=None
        time.sleep(.2)
    raise RuntimeError('Unlocked setup did not settle before the alarm trial')

def reboot_same_device():
    """Observe an actual new kernel boot; restart only a stopped cloud AVD, preserving userdata."""
    import socket
    before=adb('shell','cat','/proc/sys/kernel/random/boot_id').strip()
    if not re.fullmatch(r'[0-9a-f-]{36}',before): raise RuntimeError('Cannot establish pre-reboot boot ID')
    (REPORT/'reboot-boot-id-before.txt').write_text(before+'\n',encoding='utf-8')
    try:
        adb('reboot',timeout=10,check=False)
    except subprocess.TimeoutExpired:
        print('ADB reboot transport timed out; observing kernel boot and cloud emulator state.',flush=True)
    deadline=time.monotonic()+240
    relaunched=False
    after=''
    while time.monotonic()<deadline:
        port_open=False
        try:
            with socket.create_connection(('127.0.0.1',5554),timeout=1): port_open=True
        except OSError:
            pass
        if not port_open and not relaunched:
            # Some emulator builds terminate the host process on guest reboot.
            # Do not wipe, recreate, reinstall or launch the app during restoration.
            processes=subprocess.run(['pgrep','-f','(emulator|qemu-system).*-avd test'],capture_output=True,text=True)
            if processes.returncode==1:
                if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':
                    raise RuntimeError('AVD restart is restricted to the disposable cloud runner')
                binary=Path(os.environ['ANDROID_HOME'])/'emulator/emulator'
                with (REPORT/'reboot-emulator.log').open('w',encoding='utf-8') as output:
                    subprocess.Popen([str(binary),'-port','5554','-avd','test','-no-window','-no-audio',
                        '-no-snapshot','-gpu','swiftshader_indirect','-no-boot-anim','-accel','on'],
                        stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
                relaunched=True
                print('Cloud emulator process exited; cold-starting the SAME AVD with its existing userdata.',flush=True)
        try:
            completed=adb('shell','getprop','sys.boot_completed',timeout=5,check=False).strip()=='1'
            if completed:
                after=adb('shell','cat','/proc/sys/kernel/random/boot_id',timeout=5,check=False).strip()
                if re.fullmatch(r'[0-9a-f-]{36}',after) and after!=before:
                    (REPORT/'reboot-host-observation.json').write_text(json.dumps({
                        'before_boot_id':before,'after_boot_id':after,'host_avd_relaunched':relaunched,
                        'userdata_preserved':True},indent=2),encoding='utf-8')
                    record('reboot_restore.boot_id_changed',True)
                    return True
        except subprocess.TimeoutExpired:
            pass
        time.sleep(2)
    record('reboot_restore.boot_id_changed',False,'No completed new kernel boot observed')
    return False

def notification_switch(enabled):
    """Use Android Settings to change the real package notification switch."""
    import xml.etree.ElementTree as ET
    # Setup only: after removing the test PIN, SystemUI can retain its old lock surface.
    # Cycle the display and dismiss it before opening Settings, never during an alarm trial.
    adb('shell','input','keyevent','223')
    time.sleep(.5)
    adb('shell','input','keyevent','224')
    until=time.monotonic()+10
    while time.monotonic()<until:
        adb('shell','wm','dismiss-keyguard',check=False)
        adb('shell','input','keyevent','82')
        if keyguard(adb('shell','dumpsys','window','policy')) is False: break
        adb('shell','input','swipe','540','1500','540','400','300')
        time.sleep(.4)
    if keyguard(adb('shell','dumpsys','window','policy')) is not False:
        raise RuntimeError('Could not restore an unlocked Settings setup after the test PIN')
    adb('shell','input','keyevent','3')
    adb('shell','am','start','-W','-a','android.settings.APP_NOTIFICATION_SETTINGS',
        '--es','android.provider.extra.APP_PACKAGE',PACKAGE)
    def read_switch():
        adb('shell','uiautomator','dump','/sdcard/feishu-notification-ui.xml')
        raw=adb('shell','cat','/sdcard/feishu-notification-ui.xml')
        (REPORT/('notification-settings-'+str(enabled)+'.xml')).write_text(raw,encoding='utf-8')
        root=ET.fromstring(raw[raw.index('<?xml'):])
        candidates=[n for n in root.iter('node') if n.get('class')=='android.widget.Switch'
                    and n.get('package')=='com.android.settings' and n.get('enabled')=='true']
        if not candidates: raise RuntimeError('Package notification switch was not visible in Settings')
        # The master switch is the topmost enabled Switch on the package notification page.
        def bounds(n): return list(map(int,re.findall(r'\d+',n.get('bounds',''))))
        candidates.sort(key=lambda n:bounds(n)[1])
        return candidates[0],bounds(candidates[0])
    for attempt in range(4):
        try:
            switch,bounds=read_switch()
            break
        except RuntimeError:
            if attempt==3: raise
            time.sleep(1)
    if (switch.get('checked')=='true')!=enabled:
        x1,y1,x2,y2=bounds
        adb('shell','input','tap',str((x1+x2)//2),str((y1+y2)//2))
        time.sleep(0.4)
    switch,_=read_switch()
    record('notification_switch.'+('enabled' if enabled else 'disabled'),
           (switch.get('checked')=='true')==enabled)
    adb('shell','input','keyevent','3')

def setup_case(name, route):
    global CASE_START
    control('stop')
    adb('shell', 'input', 'keyevent', '224')
    adb('shell', 'wm', 'dismiss-keyguard', check=False)  # Preparation only; before alarm registration.
    adb('shell', 'input', 'keyevent', '3')
    adb('logcat', '-b', 'all', '-c')
    CASE_START = datetime.datetime.fromtimestamp(float(adb('shell','date','+%s').strip()), datetime.timezone.utc)
    control('test_' + route)
    adb('shell', 'input', 'keyevent', '223')
    wait_locked_asleep()
    before = snapshot(name + '-before')
    record(name + '.initial_asleep', screen(before['power']) == 'Asleep', screen(before['power']))
    record(name + '.initial_keyguard', keyguard(before['window policy']) is True)
    record(name + '.initial_target_not_foreground', not foreground(before['activity activities']))

def expect_failure(name, stage):
    time.sleep(22)
    after = snapshot(name + '-after')
    rows = events(name)
    triggered = {r['run'] for r in rows if r.get('stage') == 'trigger' and r.get('status') == 'OK'}
    current = [r for r in rows if r.get('run') in triggered]
    record(name + '.alarm_delivered', len(triggered) == 1)
    record(name + '.explicit_failure', any(r.get('stage') == stage and r.get('status') == 'FAIL' for r in current))
    record(name + '.no_launch_request', not any(r.get('stage') == 'launch' and r.get('status') == 'REQUESTED' for r in current))
    record(name + '.keyguard_retained', keyguard(after['window policy']) is True)
    record(name + '.target_not_foreground', not foreground(after['activity activities']))

def assert_success(name, timeout=50, stop=True):
    reached = wait_foreground(timeout)
    time.sleep(5)
    after = snapshot(name + '-after')
    rows = events(name)
    triggered = [r['run'] for r in rows if r.get('stage') == 'trigger' and r.get('status') == 'OK']
    stages = [(r.get('stage'),r.get('status')) for r in rows if triggered and r.get('run') == triggered[0]]
    record(name + '.foreground_stable', reached and foreground(after['activity activities']))
    record(name + '.awake', screen(after['power']) == 'Awake')
    record(name + '.keyguard_dismissed', keyguard(after['window policy']) is False)
    record(name + '.single_trigger', len(triggered) == 1)
    record(name + '.unlock_before_launch',
           ('keyguard','OK') in stages and ('launch','REQUESTED') in stages and
           stages.index(('keyguard','OK')) < stages.index(('launch','REQUESTED')))
    if stop:
        control('stop')

def extended_negatives():
    # The test PIN belongs only to this fresh cloud emulator.
    control('stop')
    adb('shell','am','force-stop',TARGET)
    output = adb('shell','locksettings','set-pin','2468')
    if 'set to' not in output.lower():
        raise RuntimeError('Could not configure the temporary emulator test PIN: '+output)
    try:
        setup_case('secure_lock', 'b')
        expect_failure('secure_lock', 'keyguard')
    finally:
        control('stop')
        cleared = adb('shell','locksettings','clear','--old','2468')
        if 'cleared' not in cleared.lower():
            raise RuntimeError('Could not clear the temporary emulator PIN: '+cleared)
        adb('shell','locksettings','set-disabled','false')

    notification_switch(False)
    try:
        setup_case('notification_denied','b')
        expect_failure('notification_denied','screen')
    finally:
        notification_switch(True)
        control('stop')

    setup_case('disabled_cancel','b')
    control('stop')
    time.sleep(20)
    after=snapshot('disabled_cancel-after')
    rows=events('disabled_cancel')
    record('disabled_cancel.no_trigger',not any(r.get('stage')=='trigger' for r in rows))
    record('disabled_cancel.asleep',screen(after['power'])=='Asleep')
    record('disabled_cancel.keyguard_retained',keyguard(after['window policy']) is True)

    setup_case('process_reclaim','b')
    old=adb('shell','pidof',PACKAGE,check=False).strip()
    adb('shell','am','kill',PACKAGE)
    time.sleep(1)
    record('process_reclaim.process_killed',bool(old) and not adb('shell','pidof',PACKAGE,check=False).strip())
    assert_success('process_reclaim')


def prefs():
    import xml.etree.ElementTree as ET
    root=ET.fromstring(adb('shell','run-as',PACKAGE,'cat','shared_prefs/wake.xml'))
    return {node.attrib['name']: ((node.text or '') if node.tag=='string' else node.attrib.get('value'))
            for node in root}

def configure(minutes, days=(1,2,3,4,5,6,7)):
    adb('shell','am','broadcast','-n',PACKAGE+'/dev.feishuwake.DebugControlReceiver',
        '--es','op','configure','--ez','enabled','true','--eia','minutes',','.join(map(str,minutes)),
        '--eia','days',','.join(map(str,days)))
    state=prefs()
    config=json.loads(state['config'])
    if not config['enabled'] or sorted(config['minutes'])!=sorted(minutes):
        raise RuntimeError('Configuration was not persisted by the debug setup entry')
    return int(state['nextDue'])/1000

def clock_minutes(offsets):
    # Read the emulator's actual wall clock and local HH:mm; do not assume host time zone.
    stamp,hour,minute=map(int,adb('shell','date','+%s,%H,%M').strip().split(','))
    now=float(stamp)
    local=hour*60+minute
    # Leave at least 20 seconds for preparation even near a minute boundary.
    shift=1 if now%60>40 else 0
    return [int((local+offset+shift)%1440) for offset in offsets], [int(now//60)*60+(offset+shift)*60 for offset in offsets]

def before_schedule():
    global CASE_START
    control('stop')
    prepare_unlocked()
    adb('logcat','-b','all','-c')
    CASE_START=datetime.datetime.fromtimestamp(float(adb('shell','date','+%s').strip()),datetime.timezone.utc)

def sleep_assert(name):
    adb('shell','input','keyevent','223')
    wait_locked_asleep()
    state=snapshot(name+'-before')
    record(name+'.initial_asleep',screen(state['power'])=='Asleep')
    record(name+'.initial_keyguard',keyguard(state['window policy']) is True)
    record(name+'.initial_target_not_foreground',not foreground(state['activity activities']))

def wait_wall(timestamp):
    while True:
        remaining=timestamp-float(adb('shell','date','+%s').strip())
        if remaining<=0: return
        time.sleep(min(5,remaining))

def unlocked_observation():
    """Classify the platform's unlocked behavior without claiming automatic success."""
    global CASE_START
    before_schedule()
    adb('shell','settings','put','system','screen_off_timeout','120000')
    control('test_b')
    time.sleep(40)
    after=snapshot('unlocked-after')
    rows=events('unlocked')
    triggered={r['run'] for r in rows if r.get('stage')=='trigger' and r.get('status')=='OK'}
    current=[r for r in rows if r.get('run') in triggered]
    launched=any(r.get('stage')=='launch' and r.get('status')=='REQUESTED' for r in current)
    failed=any(r.get('stage')=='screen' and r.get('status')=='FAIL' for r in current)
    auto=launched and foreground(after['activity activities'])
    deferred=not launched and failed and not foreground(after['activity activities'])
    record('unlocked.alarm_delivered',len(triggered)==1)
    record('unlocked.behavior_classified',auto or deferred,
           'AUTO_FOREGROUND' if auto else 'HEADS_UP_ONLY_REQUIRES_USER_TAP' if deferred else 'UNEXPECTED_STATE')
    record('unlocked.keyguard_remains_dismissed',keyguard(after['window policy']) is False)
    control('stop')
    adb('shell','settings','put','system','screen_off_timeout','30000')

def recurrence_matrix():
    global CASE_START
    before_schedule()
    minutes,due=clock_minutes((1,2))
    actual=configure(minutes)
    record('multiple_alarms.first_due',abs(actual-due[0])<1)
    sleep_assert('multiple_first')
    assert_success('multiple_first',timeout=100,stop=False)
    state=prefs()
    record('multiple_alarms.second_registered',abs(int(state['nextDue'])/1000-due[1])<1)
    adb('shell','input','keyevent','3')
    CASE_START=datetime.datetime.fromtimestamp(float(adb('shell','date','+%s').strip()),datetime.timezone.utc)
    sleep_assert('multiple_second')
    assert_success('multiple_second',timeout=100,stop=False)
    record('multiple_alarms.next_day',int(prefs()['nextDue'])/1000>due[1]+3600)
    # Observe past the end of the run to detect an immediate duplicate trigger.
    time.sleep(8)
    rows=events('multiple_second-final')
    record('multiple_alarms.no_duplicate',sum(r.get('stage')=='trigger' and r.get('status')=='OK' for r in rows)==1)
    control('stop')

    before_schedule()
    minutes,due=clock_minutes((1,2))
    configure(minutes)
    control('stop')
    sleep_assert('disabled_recurring')
    wait_wall(due[0]+8)
    state=snapshot('disabled_recurring-after')
    rows=events('disabled_recurring')
    record('disable_cancel.no_execution',not any(r.get('stage')=='trigger' for r in rows) and screen(state['power'])=='Asleep')
    record('disable_cancel.state_cleared',int(prefs()['nextDue'])==0 and prefs()['alarmToken']=='')
    # Enabling is a user action: prepare the UI state before enabling, then sleep again.
    prepare_unlocked()
    control('enable')
    CASE_START=datetime.datetime.fromtimestamp(float(adb('shell','date','+%s').strip()),datetime.timezone.utc)
    record('reenable.next_due',abs(int(prefs()['nextDue'])/1000-due[1])<1)
    sleep_assert('reenable')
    assert_success('reenable',timeout=100)

    before_schedule()
    minutes,due=clock_minutes((1,2))
    configure([minutes[0]])
    configure([minutes[1]])
    sleep_assert('edit_cancel_old')
    wait_wall(due[0]+8)
    rows=events('edit_cancel_old')
    record('edit_cancel_old.no_old_trigger',not any(r.get('stage')=='trigger' for r in rows))
    assert_success('edit_new_time',timeout=100)

    before_schedule()
    minutes,due=clock_minutes((5,6))
    configure(minutes)
    old_token=prefs()['alarmToken']
    booted=reboot_same_device()
    record('reboot_restore.booted',booted)
    if not booted: raise RuntimeError('Emulator did not reboot in time')
    # No app launch after reboot: recovery must come from BOOT_COMPLETED.
    until=time.monotonic()+45
    state=prefs()
    while state['alarmToken']==old_token and time.monotonic()<until:
        time.sleep(1)
        state=prefs()
    adb('shell','am','get-standby-bucket',PACKAGE,check=False)
    record('reboot_restore.token_renewed',bool(state['alarmToken']) and state['alarmToken']!=old_token)
    record('reboot_restore.schedule_present',abs(int(state['nextDue'])/1000-due[0])<1)
    rows=events('reboot_restore')
    record('reboot_restore.broadcast_logged',any(r.get('stage')=='restore' and 'BOOT_COMPLETED' in r.get('detail','') for r in rows))
    sleep_assert('reboot_restore')
    assert_success('reboot_restore',timeout=max(30,int(due[0]-time.time()+45)))

    before_schedule()
    minutes,due=clock_minutes((1,3))
    configure(minutes)
    adb('shell','am','force-stop',PACKAGE)
    sleep_assert('force_stop')
    wait_wall(due[0]+8)
    rows=events('force_stop')
    record('force_stop.no_execution',not any(r.get('stage')=='trigger' for r in rows))
    prepare_unlocked()
    adb('shell','am','start','-W','-n',PACKAGE+'/dev.feishuwake.MainActivity')
    state=prefs()
    record('force_stop_recovery.next_registered',abs(int(state['nextDue'])/1000-due[1])<1)
    adb('shell','input','keyevent','3')
    CASE_START=datetime.datetime.fromtimestamp(float(adb('shell','date','+%s').strip()),datetime.timezone.utc)
    sleep_assert('force_stop_recovery')
    assert_success('force_stop_recovery',timeout=max(30,int(due[1]-time.time()+45)))

try:
    if adb('shell', 'getprop', 'ro.build.version.sdk').strip() != '30':
        raise RuntimeError('Expected Android API 30')
    if adb('shell', 'getprop', 'sys.boot_completed').strip() != '1':
        raise RuntimeError('Android has not completed boot')
    record('api30_boot', True)
    for path in (ROOT/'app/build/outputs/apk/debug/app-debug.apk',
                 ROOT/'app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk'):
        adb('install', '-r', str(path), timeout=120)
    if args.target == 'mock':
        adb('install', '-r', str(ROOT/'testtarget/build/outputs/apk/debug/testtarget-debug.apk'), timeout=120)
    if args.target == 'feishu':
        official = Path(os.environ['RUNNER_TEMP']) / 'official-feishu.apk'
        if not official.is_file():
            raise RuntimeError('Verified official Feishu APK is missing on the cloud runner')
        adb('install', '-r', str(official), timeout=240)
    # Setup only: a preceding test/install may have allowed the normal screen timeout.
    # The actual background alarm trial still establishes and asserts a fresh locked/asleep state.
    adb('shell', 'input', 'keyevent', '224')
    adb('shell', 'wm', 'dismiss-keyguard')
    started = adb('shell', 'am', 'start', '-W', '-n', PACKAGE + '/dev.feishuwake.MainActivity')
    record('install_launch', 'Status: ok' in started)
    control(args.target)
    if not adb('shell', 'pm', 'path', TARGET, check=False).strip().startswith('package:'):
        raise RuntimeError('Target application is not installed: ' + TARGET)
    adb('shell', 'locksettings', 'set-disabled', 'false')
    adb('shell', 'settings', 'put', 'secure', 'lock_screen_lock_after_timeout', '0')
    adb('shell', 'settings', 'put', 'global', 'stay_on_while_plugged_in', '0')
    adb('shell', 'settings', 'put', 'system', 'screen_off_timeout', '30000')

    if args.extended:
        # First alarm for this fresh install: do not shorten the platform's Doze quota.
        adb('shell','dumpsys','battery','unplug')
        try:
            setup_case('doze', 'b')
            adb('shell','dumpsys','deviceidle','force-idle')
            idle=adb('shell','dumpsys','deviceidle')
            (REPORT/'doze-state-before.txt').write_text(idle,encoding='utf-8')
            record('doze.deep_idle_observed','mState=IDLE' in idle)
            assert_success('doze',timeout=100)
        finally:
            adb('shell','dumpsys','deviceidle','unforce',check=False)
            adb('shell','dumpsys','battery','reset',check=False)
        battery=adb('shell','dumpsys','battery')
        record('charging_state_observed','AC powered: true' in battery or 'USB powered: true' in battery)

    for route in args.routes:
        name = 'screen_off_route_' + route
        setup_case(name, route)
        reached = wait_foreground()
        if reached:
            time.sleep(5)  # Detect an immediate target crash or task returning to another app.
        after = snapshot(name + '-after')
        rows = events(name)
        record(name + '.foreground', reached and foreground(after['activity activities']))
        record(name + '.awake', screen(after['power']) == 'Awake', screen(after['power']))
        record(name + '.keyguard_dismissed', keyguard(after['window policy']) is False)
        triggered = [r['run'] for r in rows if r.get('stage') == 'trigger' and r.get('status') == 'OK']
        stages = [(r.get('stage'), r.get('status')) for r in rows if triggered and r.get('run') == triggered[0]]
        record(name + '.alarm_delivered', ('trigger', 'OK') in stages)
        record(name + '.unlock_before_launch',
               ('keyguard', 'OK') in stages and ('launch', 'REQUESTED') in stages and
               stages.index(('keyguard', 'OK')) < stages.index(('launch', 'REQUESTED')))
        control('stop')

    if args.extended:
        unlocked_observation()
        extended_negatives()
        recurrence_matrix()

    # Device-side assertions are separate from the background Activity launch trials.
    adb('shell', 'input', 'keyevent', '224')
    adb('shell', 'wm', 'dismiss-keyguard', check=False)
    result = adb('shell', 'am', 'instrument', '-w', '-r', '-e', 'class',
                 ('dev.feishuwake.CoreInstrumentedTest#configRoundTripAndCancellation,'
                  'dev.feishuwake.CoreInstrumentedTest#automationSwitchSchedulesAndCancels'),
                 PACKAGE + '.test/androidx.test.runner.AndroidJUnitRunner', timeout=120)
    (REPORT/'instrumentation.txt').write_text(result,encoding='utf-8')
    print(result,flush=True)
    record('instrumentation_config_cancel', 'OK (2 tests)' in result and 'FAILURES' not in result)
except Exception as error:
    checks['blocked'] = {'status': 'FAIL', 'detail': type(error).__name__ + ': ' + str(error)}
    print(checks['blocked'], flush=True)
finally:
    try:
        control('stop')
    except Exception:
        pass
    log.close()
    result = {'target': args.target, 'checks': checks, 'release_eligible': False,
              'extended_matrix': args.extended,
              'note': 'API 30 emulator only; no realme or attendance claim. Forced Doze is not natural long-duration standby.'}
    (REPORT/'android-host-results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False), flush=True)
    if not checks or any(row['status'] != 'PASS' for row in checks.values()):
        sys.exit(1)
