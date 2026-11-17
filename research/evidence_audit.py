"""Summarize a prior cloud test artifact without moving logs to the user's PC."""
import io
import os
import re
import zipfile
from urllib.error import HTTPError
from urllib.request import build_opener, HTTPRedirectHandler, Request, urlopen
from urllib.parse import urlparse
if os.environ.get('GITHUB_ACTIONS') != 'true':
    raise SystemExit('Cloud runner required')
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None
endpoint='https://api.github.com/repos/Kok1Ne/feishu-wake/actions/artifacts/14307580296/zip'
request=Request(endpoint,headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json'})
try:
    response=build_opener(NoRedirect).open(request, timeout=30)
    archive=response.read()
except HTTPError as error:
    if error.code != 302:
        raise
    url=error.headers['Location']
    if urlparse(url).scheme != 'https':
        raise SystemExit('HTTPS artifact redirect required')
    # The signed artifact download must NOT receive the GitHub authorization header.
    with urlopen(url,timeout=30) as response:
        archive=response.read(20_000_000)
with zipfile.ZipFile(io.BytesIO(archive)) as z:
    for name in z.namelist():
        if name.endswith(('acceleration.txt','disk-before.txt','disk-after.txt','lint-results-debug.txt')):
            print('EVIDENCE_FILE',name,flush=True)
            print(z.read(name).decode('utf-8','replace')[-12000:],flush=True)
        elif name.endswith(('screen_off_route_a-after-alarm.txt','screen_off_route_a-logcat.txt','logcat.txt')):
            text=z.read(name).decode('utf-8','replace')
            lines=text.splitlines()
            print('EVIDENCE_FILE',name,flush=True)
            selected=set()
            for i,line in enumerate(lines):
                if re.search(r'feishuwake|alarm-direct|Background activity|Background start|START u0|Abort|balCode',line,re.I):
                    selected.update(range(max(0,i-2), min(len(lines),i+3)))
            for i in sorted(selected):
                print(lines[i],flush=True)
