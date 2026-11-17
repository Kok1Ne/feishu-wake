"""Reuse the completed full cloud matrix only for the exact source commit."""
import hashlib,io,json,os,re,urllib.request,urllib.error,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if os.environ.get('GITHUB_ACTIONS')!='true': raise SystemExit('Cloud-only evidence import')
run_id=os.environ.get('FEISHU_EVIDENCE_RUN_ID','')
if not re.fullmatch(r'[0-9]+',run_id): raise SystemExit('A completed verification run ID is required')
repo=os.environ['GITHUB_REPOSITORY']
if repo!='Kok1Ne/feishu-wake': raise SystemExit('Unexpected evidence repository')
headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'FeishuWake-evidence-import'}
base='https://api.github.com/repos/'+repo
def api(path):
    with urllib.request.urlopen(urllib.request.Request(base+path,headers=headers),timeout=60) as response:
        return json.load(response)
run=api('/actions/runs/'+run_id)
if run['status']!='completed' or run['conclusion']!='success' or run['head_sha']!=os.environ['GITHUB_SHA'] or run['path']!='.github/workflows/android11-core.yml':
    raise SystemExit('Full verification must have succeeded for this exact commit')
items=api('/actions/runs/'+run_id+'/artifacts')['artifacts']
items=[a for a in items if a['name'].startswith('android11-core-evidence-'+run_id+'-') and not a['expired']]
if not items: raise SystemExit('Completed verification artifact is unavailable')
artifact=max(items,key=lambda a:a['id'])
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None
opener=urllib.request.build_opener(NoRedirect())
request=urllib.request.Request(artifact['archive_download_url'],headers=headers)
try:
    with opener.open(request,timeout=60) as response: archive=response.read(100_000_001)
except urllib.error.HTTPError as error:
    if error.code not in (301,302,303,307,308): raise
    location=error.headers['Location']
    if not location.startswith('https://'): raise SystemExit('Insecure artifact redirect')
    # Do not forward GitHub authorization to the signed artifact storage URL.
    with urllib.request.urlopen(urllib.request.Request(location,headers={'User-Agent':'FeishuWake-evidence-import'}),timeout=120) as response:
        archive=response.read(100_000_001)
if len(archive)>100_000_000 or 'sha256:'+hashlib.sha256(archive).hexdigest()!=artifact.get('digest'):
    raise SystemExit('Verification artifact size/digest mismatch')
allowed=('reports/ci/','app/build/reports/tests/testDebugUnitTest/','app/build/test-results/testDebugUnitTest/','app/build/reports/lint-results-debug.')
with zipfile.ZipFile(io.BytesIO(archive)) as z:
    if sum(x.file_size for x in z.infolist())>500_000_000: raise SystemExit('Evidence archive too large')
    for info in z.infolist():
        if info.is_dir(): continue
        if not info.filename.startswith(allowed): raise SystemExit('Unexpected evidence file: '+info.filename)
        destination=(ROOT/info.filename).resolve()
        if not destination.is_relative_to(ROOT): raise SystemExit('Evidence path escaped workspace')
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes(z.read(info))
out=ROOT/'reports/release-build'
out.mkdir(parents=True,exist_ok=True)
(out/'verification-provenance.json').write_text(json.dumps({'run_id':run['id'],'head_sha':run['head_sha'],
    'conclusion':run['conclusion'],'html_url':run['html_url'],'artifact_id':artifact['id'],'artifact_digest':artifact['digest']},indent=2),encoding='utf-8')
print('Verified exact-commit cloud evidence imported from run '+run_id)
