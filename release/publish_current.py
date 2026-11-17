"""Publish only the signed, tested files from this exact cloud workflow."""
import hashlib,json,os,subprocess,time,urllib.error,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'deliverables'
REPO='Kok1Ne/feishu-wake'
TAG='v1.0.1'
if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('GITHUB_REPOSITORY')!=REPO:
    raise SystemExit('Publication is restricted to this cloud repository')
def gh(*args,body=None):
    p=subprocess.run(['gh',*args],input=None if body is None else json.dumps(body),capture_output=True,text=True)
    if p.returncode: raise RuntimeError('GitHub operation failed: '+p.stderr)
    return p.stdout
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
expected={}
for line in (OUT/'SHA256SUMS.txt').read_text().splitlines():
    digest,name=line.split('  ',1)
    if Path(name).name!=name or sha(OUT/name)!=digest: raise SystemExit('Delivery checksum mismatch')
    expected[name]=digest
expected['SHA256SUMS.txt']=sha(OUT/'SHA256SUMS.txt')
required={'FeishuWake-1.0.1.apk','APK-SIGNATURE.txt','USER_GUIDE_ZH.md','ANDROID11_COMPATIBILITY.md',
          'SOURCE_COMMIT.txt','FeishuWake-AndroidStudio-source.zip','FeishuWake-cloud-evidence.zip',
          'CLOUD_TEST_REPORT_ZH.md','SHA256SUMS.txt'}
if set(expected)!=required: raise SystemExit('Unexpected deliverables')
commit=os.environ['GITHUB_SHA']
if (OUT/'SOURCE_COMMIT.txt').read_text().strip()!=commit: raise SystemExit('Source mismatch')
identity=json.loads((ROOT/'reports/release-build/identity.json').read_text())
smoke=json.loads((ROOT/'reports/release-device/results.json').read_text())
gate=json.loads((ROOT/'release-evidence.json').read_text())
if identity['version']!='1.0.1' or identity['apk_sha256']!=expected['FeishuWake-1.0.1.apk']:
    raise SystemExit('Unexpected release identity')
if smoke['source_commit']!=commit or any(v!='PASS' for v in smoke['checks'].values()):
    raise SystemExit('Signed APK verification is incomplete')
body=f"""## Feishu Wake 1.0.1 · Android 11

- 测试前检查通知、锁屏和目标应用，缺少条件时直接说明原因。
- 分别记录通知提交、页面创建、页面进入前台，以及失败时的系统状态。
- 可选兼容唤醒：Android 11 用户主动授权后，全屏通知未打开页面时尝试另一条系统允许的启动路径；默认关闭，不读取或截取屏幕。
- 全新中文界面：定时、记录、设置三个页面；执行记录按任务归类，详细步骤可展开，时间使用手机本地时区。

### 安装与使用
从下面 Assets 下载 **FeishuWake-1.0.1.apk**，直接覆盖安装 1.0.0，保留设置，无需卸载。
在设置中允许通知与锁屏显示。此前出现“系统未打开唤醒页面”时，可主动启用“兼容唤醒”并授权“显示在其他应用上层”，随后进行一次 15 秒息屏测试；成功后再启用长期定时。
如仍失败，请导出诊断 JSON，按同一次任务定位，不需要重复截图。

### 云端验证
同一源码提交的 Android 11 完整矩阵、Gradle 编译、JVM 测试、Instrumentation 和 lint 均通过。
正式签名包另在新的 API 30 模拟器复测：真实飞书前台、解锁顺序、兼容唤醒及 **1.0.0 → 1.0.1 覆盖安装与配置恢复**。
- [完整矩阵](https://github.com/{REPO}/actions/runs/{gate['run_id']})
- [正式包复测](https://github.com/{REPO}/actions/runs/{os.environ['GITHUB_RUN_ID']})
- 源码：{commit}
- APK SHA-256：{identity['apk_sha256']}
- 固定证书 SHA-256：{identity['certificate_sha256']}

模拟器测试不代表所有 Android 11 手机均已通过；不同设备的后台、通知和锁屏策略仍需确认。
本软件不操作考勤，不绕过安全密码；启动请求、前台观察与打卡成功是不同状态。
完整日志、静态检查、签名校验、源码及中文说明均包含在附件中。
"""
release=json.loads(gh('api','--method','POST',f'repos/{REPO}/releases','--input','-',body={
    'tag_name':TAG,'target_commitish':commit,'name':'Feishu Wake 1.0.1 · Android 11',
    'body':body,'draft':True,'prerelease':False}))
rid=release['id']
gh('release','upload',TAG,*[str(OUT/name) for name in sorted(required)],'--repo',REPO)
assets=json.loads(gh('api',f'repos/{REPO}/releases/{rid}/assets'))
if {x['name'] for x in assets}!=required: raise SystemExit('Uploaded assets differ')
for asset in assets:
    name=asset['name']
    if asset['size']!=(OUT/name).stat().st_size or asset.get('digest')!='sha256:'+expected[name]:
        raise SystemExit('Remote asset checksum mismatch: '+name)
published=json.loads(gh('api','--method','PATCH',f'repos/{REPO}/releases/{rid}','--input','-',body={'draft':False,'make_latest':'true'}))
if published['draft']: raise SystemExit('Release still draft')
# Re-read public URLs after publication: the earlier asset objects came from a draft.
public_assets=json.loads(gh('api',f'repos/{REPO}/releases/{rid}/assets'))
apk=next(x for x in public_assets if x['name']=='FeishuWake-1.0.1.apk')
for attempt in range(6):
    try:
        with urllib.request.urlopen(urllib.request.Request(apk['browser_download_url'],headers={'User-Agent':'FeishuWake-cloud-validation'}),timeout=90) as response:
            digest=hashlib.sha256(response.read()).hexdigest()
        break
    except urllib.error.HTTPError as error:
        if error.code not in (404,429,500,502,503,504) or attempt==5: raise
        time.sleep(2*(attempt+1))
if digest!=expected['FeishuWake-1.0.1.apk']: raise SystemExit('Published download checksum mismatch')
print('Published and verified: '+published['html_url'])
