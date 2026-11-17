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
    time.sleep(1)
    before = snapshot(name + '-before')
    record(name + '.initial_asleep', screen(before['power']) == 'Asleep', screen(before['power']))
    record(name + '.initial_keyguard', keyguard(before['window policy']) is True)
    record(name + '.initial_target_not_foreground', not foreground(before['activity activities']))

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

    # Device-side assertions are separate from the background Activity launch trials.
    adb('shell', 'input', 'keyevent', '224')
    adb('shell', 'wm', 'dismiss-keyguard', check=False)
    result = adb('shell', 'am', 'instrument', '-w', '-r', '-e', 'class',
                 'dev.feishuwake.CoreInstrumentedTest#configRoundTripAndCancellation',
                 PACKAGE + '.test/androidx.test.runner.AndroidJUnitRunner', timeout=120)
    record('instrumentation_config_cancel', 'OK (1 test)' in result and 'FAILURES' not in result)
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
              'note': 'Core probe only. Fixture evidence cannot establish real Feishu or realme compatibility.'}
    (REPORT/'android-host-results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False), flush=True)
    if not checks or any(row['status'] != 'PASS' for row in checks.values()):
        sys.exit(1)
