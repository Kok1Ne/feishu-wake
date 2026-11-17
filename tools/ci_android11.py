"""Run the existing partial core probe on an isolated API 30 CI emulator.

Collect evidence while the emulator is alive, including when the probe fails.
A successful fixture probe never qualifies this project for Release.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
TARGET = os.environ.get('FEISHU_PROBE_TARGET', 'mock')
EXTENDED = os.environ.get('FEISHU_PROBE_EXTENDED') == '1'
if TARGET not in ('mock', 'feishu'):
    raise SystemExit('Unknown probe target')
REPORT = ROOT / 'reports' / 'ci' / TARGET
SERIAL = 'emulator-5554'


def capture(command, path, timeout=40):
    """Record a best-effort diagnostic without hiding the primary test result."""
    try:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=timeout)
        path.write_bytes(result.stdout + result.stderr)
        return result.returncode
    except (OSError, subprocess.TimeoutExpired) as error:
        path.write_text(str(error), encoding='utf-8')
        return -1


def main():
    REPORT.mkdir(parents=True, exist_ok=True)
    adb = shutil.which('adb')
    status = {
        'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'source_commit': os.environ.get('GITHUB_SHA'),
        'run_id': os.environ.get('GITHUB_RUN_ID'),
        'run_attempt': os.environ.get('GITHUB_RUN_ATTEMPT'),
        'target': TARGET,
        'release_eligible': False,
        'scope': 'Extended API 30 acceptance matrix' if EXTENDED else 'Core API 30 probe',
        'unverified': ['See individual checks for actual results', 'natural long-duration standby', 'realme UI 2.0'],
    }
    result_code = 1
    try:
        if not adb:
            raise RuntimeError('ADB is missing from PATH')
        adb_base = [adb, '-P', '5037', '-s', SERIAL]
        capture([adb, 'version'], REPORT / 'adb-version.txt')
        emulator = shutil.which('emulator')
        if not emulator:
            sdk = os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT')
            if sdk and (Path(sdk) / 'emulator' / 'emulator').is_file():
                emulator = str(Path(sdk) / 'emulator' / 'emulator')
        if not emulator or capture([emulator, '-accel-check'], REPORT / 'acceleration.txt') != 0:
            raise RuntimeError('No usable hardware acceleration; do not fall back to software')
        capture(adb_base + ['shell', 'getprop'], REPORT / 'device-properties.txt')
        capture(adb_base + ['shell', 'dumpsys', 'window', 'policy'], REPORT / 'keyguard-before.txt')
        capture(adb_base + ['logcat', '-c'], REPORT / 'logcat-clear.txt')
        command=[sys.executable, str(ROOT/'tools/verify_android.py'),
                 '--adb',adb,'--port','5037','--serial',SERIAL,
                 '--target',TARGET,'--report-dir',str(REPORT)] + (['--extended'] if EXTENDED else [])
        with (REPORT/'probe-output.log').open('w',encoding='utf-8') as output:
            proc=subprocess.Popen(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                                  text=True,encoding='utf-8',errors='replace',bufsize=1)
            def stream():
                for line in proc.stdout:
                    output.write(line);output.flush()
                    print(line,end='',flush=True)
            reader=threading.Thread(target=stream,daemon=True)
            reader.start()
            try:
                result_code=proc.wait(timeout=1500 if EXTENDED else 420)
            except subprocess.TimeoutExpired:
                proc.kill();proc.wait()
                raise
            finally:
                reader.join(timeout=10)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        status['blocked'] = str(error)
        print(str(error), file=sys.stderr)
        result_code = 1
    finally:
        if adb:
            adb_base = [adb, '-P', '5037', '-s', SERIAL]
            for service in ('power', 'window', 'activity', 'alarm', 'deviceidle', 'notification'):
                capture(adb_base + ['shell', 'dumpsys', service], REPORT / (service + '.txt'))
            capture(adb_base + ['logcat', '-d', '-v', 'threadtime'], REPORT / 'logcat.txt')
        if result_code != 0 and (REPORT / 'logcat.txt').is_file():
            lines = (REPORT / 'logcat.txt').read_text(encoding='utf-8', errors='replace').splitlines()
            diagnostic = [line for line in lines if any(word in line for word in
                          ('FeishuWake', 'ActivityTaskManager', 'FATAL EXCEPTION', 'ANR in', 'lowmemorykiller'))]
            print('FAILURE_DEVICE_LOGS\\n' + '\\n'.join(diagnostic[-100:]), flush=True)
        status['probe_exit_code'] = result_code
        status['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        (REPORT / 'ci-status.json').write_text(json.dumps(status, indent=2), encoding='utf-8')
        hashes = {str(path.relative_to(REPORT)): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in sorted(REPORT.rglob('*'))
                  if path.is_file() and path.name != 'SHA256.json'}
        (REPORT / 'SHA256.json').write_text(json.dumps(hashes, indent=2), encoding='utf-8')
    return result_code


if __name__ == '__main__':
    raise SystemExit(main())
