"""Fetch the official public Android package on a disposable cloud runner only.
The package is inspected, never redistributed as a project artifact.
API discovered in the script linked by https://www.feishu.cn/download .
"""
import hashlib
import json
import os
import re
import html
from pathlib import Path
import subprocess
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import zipfile

if os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted':
    raise SystemExit('This inspection runs only on a GitHub-hosted cloud runner.')
API = 'https://www.feishu.cn/api/package_info?platform=2'
HEADERS = {'User-Agent': 'Mozilla/5.0 (Linux; Android 11; Pixel 2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36', 'Accept': '*/*', 'Referer': 'https://www.feishu.cn/download'}
with urlopen(Request(API, headers=HEADERS), timeout=30) as response:
    metadata = json.load(response)
data = metadata.get('data') or {}
print('OFFICIAL_METADATA', json.dumps({k:data.get(k) for k in ('version_number','weight','hash','release_time')}),
      'code=', metadata.get('code'), flush=True)
url = data.get('download_link') or ''
host = urlparse(url).hostname or ''
if host == 'zlink.toutiao.com':
    # This is the redirect service actually returned by Feishu's official package-info API.
    with urlopen(Request(url, headers=HEADERS), timeout=30) as response:
        print('OFFICIAL_SHORTLINK_FINAL', urlparse(response.url).hostname, response.headers.get('Content-Type'), flush=True)
        if 'text/html' in (response.headers.get('Content-Type') or ''):
            page = response.read(2_000_000).decode('utf-8', 'replace')
            for match in list(re.finditer(r'\.apk|download_url|downloadUrl|app_url|apk_url', page, re.I))[:25]:
                print('SHORTLINK_MATCH', page[max(0,match.start()-300):match.end()+400].replace('\n',' '), flush=True)
            print('SHORTLINK_SCRIPTS', re.findall(r'<script[^>]+src=["\']([^"\']+)', page), flush=True)
            raise SystemExit('Official shortlink returned an HTML landing page; inspect its APK link before downloading.')
        url = response.url
        host = urlparse(url).hostname or ''
if urlparse(url).scheme != 'https' or not any(host == s or host.endswith('.'+s) for s in ('feishu.cn','feishucdn.com','pstatp.com')):
    raise SystemExit('No supported official HTTPS package URL; host=' + host)
print('PACKAGE_HOST', host, flush=True)
destination = Path(os.environ['RUNNER_TEMP']) / 'official-feishu.apk'
digest = hashlib.sha256()
size = 0
with urlopen(Request(url, headers=HEADERS), timeout=60) as response, destination.open('wb') as output:
    final_host = urlparse(response.url).hostname or ''
    if not any(final_host == s or final_host.endswith('.'+s) for s in ('feishu.cn','feishucdn.com','pstatp.com')):
        raise SystemExit('Unexpected package redirect host: ' + final_host)
    while True:
        block = response.read(1024*1024)
        if not block:
            break
        size += len(block)
        if size > 800*1024*1024:
            raise SystemExit('Package exceeds cloud test download size limit')
        digest.update(block)
        output.write(block)
print('PACKAGE_BYTES', size, 'SHA256', digest.hexdigest(), flush=True)
with zipfile.ZipFile(destination) as archive:
    abis = sorted({p.split('/')[1] for p in archive.namelist() if p.startswith('lib/') and p.endswith('.so')})
    print('NATIVE_ABIS', json.dumps(abis), flush=True)
sdk = Path(os.environ['ANDROID_HOME'])
candidates = sorted((sdk/'build-tools').glob('*'), reverse=True)
for tool, arguments in (('aapt',['dump','badging']),('apksigner',['verify','--verbose','--print-certs'])):
    binary = next((p/tool for p in candidates if (p/tool).is_file()), None)
    if not binary:
        print('METADATA_TOOL_UNAVAILABLE', tool, flush=True)
        continue
    result = subprocess.run([str(binary),*arguments,str(destination)], capture_output=True, text=True, timeout=90)
    if tool == 'aapt':
        lines = [line for line in result.stdout.splitlines() if line.startswith(('package:','sdkVersion:','targetSdkVersion:','launchable-activity:','native-code:'))]
        print('\n'.join(lines), flush=True)
    else:
        print(result.stdout, result.stderr, flush=True)
    print('METADATA_EXIT', tool, result.returncode, flush=True)
destination.unlink()
