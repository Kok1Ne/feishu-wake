"""Recheck the published 1.0.1 bytes without rebuilding or changing the APK."""
import hashlib,json,os,subprocess,time,urllib.error,urllib.request,zipfile,io
from pathlib import Path
REPO='Kok1Ne/feishu-wake'
TAG='v1.0.1'
SOURCE='30b6c74cfe7dba7c8cba707d81198174d30e3f47'
APK_SHA='5ed7eb64880f141e7b17684cc1a3368ec97a71138c501a886efae406b5a45c5e'
CERT='323c450b86e5e0439bd0928e7ad574daa08fe2e5b66c13ea68aa9fe2cba96a45'
if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('GITHUB_REPOSITORY')!=REPO:
    raise SystemExit('Run this verification in the authorized cloud repository')
def gh(*args,body=None):
    p=subprocess.run(['gh',*args],input=None if body is None else json.dumps(body),capture_output=True,text=True)
    if p.returncode: raise RuntimeError(p.stderr)
    return json.loads(p.stdout)
def require(ok,message):
    if not ok: raise RuntimeError(message)
def download(url):
    for attempt in range(6):
        try:
            request=urllib.request.Request(url,headers={'User-Agent':'FeishuWake-public-download-verification','Accept':'*/*'})
            with urllib.request.urlopen(request,timeout=90) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code not in (404,429,500,502,503,504) or attempt==5: raise
            time.sleep(2*(attempt+1))
release=gh('api',f'repos/{REPO}/releases/tags/{TAG}')
require(not release['draft'] and not release['prerelease'],'Expected published final release')
assets=gh('api',f'repos/{REPO}/releases/{release["id"]}/assets')
required={'FeishuWake-1.0.1.apk','APK-SIGNATURE.txt','USER_GUIDE_ZH.md','ANDROID11_COMPATIBILITY.md',
          'SOURCE_COMMIT.txt','FeishuWake-AndroidStudio-source.zip','FeishuWake-cloud-evidence.zip',
          'CLOUD_TEST_REPORT_ZH.md','SHA256SUMS.txt'}
require({a['name'] for a in assets}==required,'Incorrect release asset list')
data={}
digests={}
for asset in assets:
    name=asset['name']
    expected_url=f'https://github.com/{REPO}/releases/download/{TAG}/{name}'
    require(asset['browser_download_url']==expected_url,'Unexpected public asset URL')
    raw=download(expected_url)  # No authorization header: exercise the public download.
    digest=hashlib.sha256(raw).hexdigest()
    require(len(raw)==asset['size'] and asset['digest']=='sha256:'+digest,'Public bytes mismatch: '+name)
    data[name]=raw
    digests[name]=digest
    print('PUBLIC_DOWNLOAD PASS '+name+' sha256='+digest,flush=True)
manifest={}
for line in data['SHA256SUMS.txt'].decode('utf-8').splitlines():
    digest,name=line.split('  ',1)
    require(name in data and digests[name]==digest,'SHA256SUMS mismatch: '+name)
    manifest[name]=digest
require(set(manifest)==required-{'SHA256SUMS.txt'},'Checksum manifest incomplete')
require(digests['FeishuWake-1.0.1.apk']==APK_SHA,'APK changed after signed-device tests')
require(data['SOURCE_COMMIT.txt'].decode().strip()==SOURCE,'Release source changed')
signature=data['APK-SIGNATURE.txt'].decode()
require('Signer #1 certificate SHA-256 digest: '+CERT in signature and
        'Verified using v2 scheme (APK Signature Scheme v2): true' in signature,'Signing verification mismatch')
with zipfile.ZipFile(io.BytesIO(data['FeishuWake-cloud-evidence.zip'])) as archive:
    require(archive.testzip() is None,'Evidence ZIP failed CRC verification')
    smoke=json.loads(archive.read('reports/release-device/results.json'))
    identity=json.loads(archive.read('reports/release-build/identity.json'))
    gate=json.loads(archive.read('release-evidence.json'))
    require(smoke['source_commit']==SOURCE and smoke['apk_sha256']==APK_SHA,'Signed-device evidence mismatch')
    require(smoke['checks'] and all(v=='PASS' for v in smoke['checks'].values()),'Signed-device tests failed')
    require(identity['source_commit']==SOURCE and identity['apk_sha256']==APK_SHA and
            identity['certificate_sha256']==CERT,'APK identity mismatch')
    require(gate['source_commit']==SOURCE and str(gate['run_id'])=='44072347613','Core acceptance source mismatch')
    require(gate['checks'] and all(v=='PASS' for v in gate['checks'].values()),'Core acceptance incomplete')
    require('BUILD SUCCESSFUL' in archive.read('reports/release-build/gradle-release.log').decode(),'Release build did not pass')
with zipfile.ZipFile(io.BytesIO(data['FeishuWake-AndroidStudio-source.zip'])) as archive:
    require(archive.testzip() is None,'Source ZIP failed CRC verification')
    require('FeishuWake-1.0.1/app/src/main/java/dev/feishuwake/MainActivity.kt' in archive.namelist(),'Source project missing')
proof={'release':release['html_url'],'source_commit':SOURCE,'apk_sha256':APK_SHA,'certificate_sha256':CERT,
       'public_downloads':digests,'signed_device_check_count':len(smoke['checks']),
       'core_checks':gate['checks'],'jvm_test_count':gate['jvm_test_count'],
       'verification_run':'https://github.com/'+REPO+'/actions/runs/'+os.environ['GITHUB_RUN_ID'],
       'note':'Published bytes verified without changing the APK. Android 11 emulator tests do not establish physical-device compatibility.'}
out=Path('reports/public-readback')
out.mkdir(parents=True,exist_ok=True)
(out/'results.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
marker='### 公开下载复核'
body=release['body'].split(marker,1)[0].rstrip()+'\n\n'+marker+'\n\n'
body+='全部 9 个附件已通过无登录公开下载、文件大小与 SHA-256 复核：[验证记录]('+proof['verification_run']+')。\n'
body+='完整矩阵和正式签名包复测均通过。首次发布流程在发布后的下载复核遇到 404，此处的独立复核确认公开附件可用；APK 未重新编译或更换。\n'
gh('api','--method','PATCH',f'repos/{REPO}/releases/{release["id"]}','--input','-',body={'body':body})
print('PUBLIC_RELEASE_VERIFIED '+release['html_url'],flush=True)
print('SIGNED_DEVICE_CHECKS '+str(len(smoke['checks'])),flush=True)
