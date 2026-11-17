"""Verify the APK and package only completed, source-bound release deliverables."""
import hashlib,json,os,re,shutil,subprocess,sys,zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
APK=ROOT/'app/build/outputs/apk/release/app-release.apk'
REPORT=ROOT/'reports/release-build'
REPORT.mkdir(parents=True,exist_ok=True)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def run(command):
    p=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace')
    if p.returncode: raise RuntimeError('Verification command failed: '+str(command)+'\n'+p.stdout+p.stderr)
    return p.stdout+p.stderr
if os.environ.get('GITHUB_ACTIONS')!='true': raise SystemExit('Release packaging is cloud-only')
if '--verify' in sys.argv:
    sdk=Path(os.environ['ANDROID_HOME'])/'build-tools/35.0.0'
    sig=run([str(sdk/'apksigner'),'verify','--verbose','--print-certs',str(APK)])
    expected=(ROOT/'signing/certificate-sha256.txt').read_text().strip()
    found=re.search(r'Signer #1 certificate SHA-256 digest: ([0-9a-f]+)',sig)
    if not found or found.group(1)!=expected or 'Verified using v2 scheme (APK Signature Scheme v2): true' not in sig:
        raise SystemExit('Release signing certificate/scheme mismatch')
    badging=run([str(sdk/'aapt'),'dump','badging',str(APK)])
    if "package: name='dev.feishuwake'" not in badging or "versionName='1.0.1'" not in badging:
        raise SystemExit('Unexpected Release identity')
    if 'application-debuggable' in badging or "uses-permission: name='android.permission.INTERNET'" in badging:
        raise SystemExit('Unexpected debug/network capability in Release')
    manifest=run([str(sdk/'aapt'),'dump','xmltree',str(APK),'AndroidManifest.xml'])
    if 'DebugControlReceiver' in manifest: raise SystemExit('Debug control leaked into Release')
    aligned=run([str(sdk/'zipalign'),'-c','-v','4',str(APK)])
    (REPORT/'signature.txt').write_text(sig,encoding='utf-8')
    (REPORT/'apk-badging.txt').write_text(badging,encoding='utf-8')
    (REPORT/'apk-manifest.txt').write_text(manifest,encoding='utf-8')
    (REPORT/'zipalign.txt').write_text(aligned,encoding='utf-8')
    (REPORT/'identity.json').write_text(json.dumps({'package':'dev.feishuwake','version':'1.0.1',
        'apk_sha256':sha(APK),'certificate_sha256':expected,'source_commit':os.environ['GITHUB_SHA']},indent=2),encoding='utf-8')
    print('Release APK verified: '+sha(APK))
elif '--package' in sys.argv:
    smoke=json.loads((ROOT/'reports/release-device/results.json').read_text())
    if not smoke['checks'] or any(s!='PASS' for s in smoke['checks'].values()) or smoke['apk_sha256']!=sha(APK):
        raise SystemExit('Signed release device checks are incomplete or APK bytes changed')
    evidence=json.loads((ROOT/'release-evidence.json').read_text())
    identity=json.loads((REPORT/'identity.json').read_text())
    if identity['apk_sha256']!=sha(APK) or identity['source_commit']!=os.environ['GITHUB_SHA']:
        raise SystemExit('Release identity changed')
    lint=ET.parse(ROOT/'app/build/reports/lint-results-release.xml').getroot()
    if any(i.get('severity') in ('Error','Fatal') for i in lint.findall('issue')):
        raise SystemExit('Release lint contains errors')
    if 'BUILD SUCCESSFUL' not in (REPORT/'gradle-release.log').read_text():
        raise SystemExit('Successful Release build log is missing')
    if smoke['source_commit']!=os.environ['GITHUB_SHA']:
        raise SystemExit('Release smoke test belongs to a different source')
    out=ROOT/'deliverables'
    out.mkdir(exist_ok=True)
    shutil.copy2(APK,out/'FeishuWake-1.0.1.apk')
    shutil.copy2(REPORT/'signature.txt',out/'APK-SIGNATURE.txt')
    shutil.copy2(ROOT/'docs/USER_GUIDE_ZH.md',out/'USER_GUIDE_ZH.md')
    shutil.copy2(ROOT/'docs/ANDROID11_COMPATIBILITY.md',out/'ANDROID11_COMPATIBILITY.md')
    (out/'SOURCE_COMMIT.txt').write_text(os.environ['GITHUB_SHA']+'\n',encoding='utf-8')
    run(['git','archive','--format=zip','--prefix=FeishuWake-1.0.1/','--output='+str(out/'FeishuWake-AndroidStudio-source.zip'),'HEAD'])
    with zipfile.ZipFile(out/'FeishuWake-cloud-evidence.zip','w',zipfile.ZIP_DEFLATED) as z:
        for folder in ['reports/ci','reports/release-build','reports/release-device','app/build/reports','app/build/test-results']:
            for p in sorted((ROOT/folder).rglob('*')):
                if p.is_file(): z.write(p,p.relative_to(ROOT).as_posix())
        z.write(ROOT/'release-evidence.json','release-evidence.json')
    rows=['# Feishu Wake 1.0.1 云端验收报告','',
        '源码提交：'+os.environ['GITHUB_SHA'],
        '运行记录：https://github.com/'+os.environ['GITHUB_REPOSITORY']+'/actions/runs/'+os.environ['GITHUB_RUN_ID'],'',
        '环境：GitHub 标准 Ubuntu 24.04 云端运行器、JDK 17、Gradle 8.9、Android SDK Platform 30/35、Build Tools 35、真实启动的 API 30 Google APIs 模拟器、KVM 硬件加速。',
        '验证目标：官方来源、安装包身份和签名经核验的真实飞书客户端；不登录账号，不验证考勤。','',
        '| 云端门槛 | 结果 |','|---|---|']
    names={'install_launch':'安装与启动','screen_off_alarm':'息屏闹钟触发','wake_screen':'点亮屏幕',
        'dismiss_swipe':'解除非安全滑动锁屏','feishu_foreground':'真实飞书进入前台','doze':'强制 Doze',
        'reboot_restore':'重启后恢复并执行','multiple_alarms':'多个定时时刻','disable_cancel':'关闭并取消任务',
        'reenable':'重新开启恢复','edit_cancel_old':'修改时间取消旧闹钟','deduplicate':'无重复执行',
        'secure_lock_refused':'安全锁屏拒绝','notification_denied':'通知关闭后明确失败',
        'process_reclaim':'进程回收后执行','force_stop_recovery':'强制停止及重新打开恢复',
        'debug_build':'开发验证包编译','unit_tests':'JVM 单元测试','android_lint':'静态检查'}
    rows += ['| '+names.get(k,k)+' | '+v+' |' for k,v in evidence['checks'].items()]
    rows += ['','正式包 Gradle 编译：BUILD SUCCESSFUL；Release lint：无 Error / Fatal。',
             '完整矩阵运行：https://github.com/'+os.environ['GITHUB_REPOSITORY']+'/actions/runs/'+evidence['run_id']]
    rows += ['','JVM 单元测试数量：'+str(evidence['jvm_test_count']), '',
        '| 正式签名包复测 | 结果 |','|---|---|']
    rows += ['| '+k+' | '+v+' |' for k,v in smoke['checks'].items()]
    rows += ['','APK SHA-256：'+identity['apk_sha256'],
        '固定签名证书 SHA-256：'+identity['certificate_sha256'],'',
        '## 结果边界','',
        '- 强制 Doze 验证的是 15 秒单次闹钟及唤醒流程；不是自然长时间待机。固定时刻采用系统可见的 setAlarmClock，重启和多次执行均按真实时钟等待验证。',
        '- 默认全屏通知在已解锁亮屏时可能仅显示横幅。可选兼容唤醒需要主动授权，相关正常、阻断和撤权场景分别收集证据。',
        '- Android 11 不同设备的自启动、后台冻结、通知和锁屏策略仍待真机确认；模拟器通过不代表手机已经通过。',
        '- 实际飞书前台由模拟器 ADB 独立核实；应用默认日志仅记启动请求，不能把它当作考勤成功。',
        '- 安全密码锁屏明确拒绝；用户强制停止后必须重新打开本应用。',
        '- 构建、lint、Instrumentation、ADB、Logcat、系统状态快照和文件校验均见 cloud-evidence 压缩包。']
    (out/'CLOUD_TEST_REPORT_ZH.md').write_text('\n'.join(rows)+'\n',encoding='utf-8')
    (out/'SHA256SUMS.txt').write_text('\n'.join(sha(p)+'  '+p.name for p in sorted(out.iterdir()) if p.is_file() and p.name!='SHA256SUMS.txt')+'\n',encoding='utf-8')
    print('Completed release package: '+str(out))
else: raise SystemExit('Expected --verify or --package')
