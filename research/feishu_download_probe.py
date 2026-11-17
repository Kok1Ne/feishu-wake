"""Inspect only public download-page assets; run on a disposable GitHub runner.
No accounts, cookies, browser profiles, or APK downloads are used here.
"""
from html.parser import HTMLParser
import json
import re
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

ROOT = 'https://www.feishu.cn/download'
class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []
        self.links = []
    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == 'script' and values.get('src'):
            self.scripts.append(urljoin(ROOT, values['src']))
        if tag == 'a' and values.get('href'):
            self.links.append(urljoin(ROOT, values['href']))

def get(url):
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': '*/*'})
    with urlopen(req, timeout=25) as response:
        data = response.read(8_000_001)
        if len(data) > 8_000_000:
            raise RuntimeError('Public text asset exceeds size limit')
        print('PUBLIC_ASSET', response.status, response.url, len(data), flush=True)
        return data.decode('utf-8', 'replace')

def inspect(text):
    # Public URLs and nearby download API implementation, not arbitrary script execution.
    matches = list(re.finditer(r'\.apk|/api/[^"\s]{0,100}(?:download|version)|download_link|download_url|downloadUrl|android_url', text, re.I))
    for hit in matches[:30]:
        print('MATCH', text[max(0,hit.start()-180):hit.end()+300].replace('\n',' '), flush=True)

page = get(ROOT)
parser = Page()
parser.feed(page)
inspect(page)
print('LINKS', json.dumps([x for x in parser.links if any(k in x.lower() for k in ('download','android','apk'))]), flush=True)
print('SCRIPTS', json.dumps(parser.scripts), flush=True)
for url in parser.scripts[:18]:
    host = urlparse(url).hostname or ''
    if not any(host == suffix or host.endswith('.'+suffix) for suffix in ('feishu.cn','feishucdn.com','pstatp.com','bytecdn.cn','bytedance.com','byteimg.com')):
        print('SKIP_OTHER_HOST', host, flush=True)
        continue
    try:
        inspect(get(url))
    except Exception as error:
        print('FETCH_FAILED', type(error).__name__, str(error), flush=True)
