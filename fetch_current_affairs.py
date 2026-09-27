# Automatic updater
# Run locally: pip install -r requirements.txt && python fetch_current_affairs.py
# For production, use the GitHub Actions workflow.
import json, os, re, hashlib
from datetime import datetime
from pathlib import Path
import requests, feedparser
from bs4 import BeautifulSoup
BASE=Path(__file__).parent; SRC=json.loads((BASE/'sources.json').read_text(encoding='utf-8'))
def clean(x): return re.sub(r'\\s+',' ',BeautifulSoup(str(x or ''),'html.parser').get_text(' ',strip=True)).strip()
def rss(s):
    f=feedparser.parse(s['url']); out=[]
    for e in f.entries[:30]:
        t=clean(e.get('title')); u=e.get('link','')
        if t and u: out.append(item(t,clean(e.get('summary') or e.get('description')),s,u,e.get('published') or datetime.now().strftime('%Y-%m-%d')))
    return out
def html(s):
    r=requests.get(s['url'],timeout=25,headers={'User-Agent':'AbhayCurrentAffairsBot/1.0'}); r.raise_for_status()
    soup=BeautifulSoup(r.text,'html.parser'); out=[]; seen=set()
    from urllib.parse import urljoin
    for a in soup.find_all('a',href=True):
        t=clean(a.get_text(' ',strip=True)); u=urljoin(s['url'],a['href'])
        if 25<=len(t)<=220 and u.startswith('http') and u not in seen:
            seen.add(u); out.append(item(t,'Official-source item. Open the source for the full notice or update.',s,u,datetime.now().strftime('%Y-%m-%d')))
        if len(out)>=20: break
    return out
def item(t,summary,s,u,d): return {'id':hashlib.sha256((t+'|'+u).encode()).hexdigest()[:16],'category':s['category'],'title':t,'summary':summary[:600],'sourceName':s['name'],'sourceUrl':u,'date':d}
def main():
    out=[]
    for s in SRC.get('rss_feeds',[]):
        try: out+=rss(s)
        except Exception as e: print('RSS error',e)
    for s in SRC.get('html_sources',[]):
        try: out+=html(s)
        except Exception as e: print('HTML error',e)
    d={'updated':datetime.now().strftime('%d %B %Y, %I:%M %p'),'items':list({x['id']:x for x in out}.values())[:80],'mcqs':[]}
    key=os.getenv('OPENAI_API_KEY')
    if key and d['items']:
        from openai import OpenAI
        c=OpenAI(api_key=key)
        prompt='Create concise original factual summaries for these current-affairs items. Do not invent facts. Return JSON array with id and summary only. '+json.dumps(d['items'],ensure_ascii=False)
        try:
            r=c.responses.create(model=os.getenv('OPENAI_MODEL','gpt-5-mini'),input=prompt)
            vals=json.loads(r.output_text); m={x['id']:x for x in d['items']}
            for x in vals:
                if x.get('id') in m: m[x['id']]['summary']=clean(x.get('summary'))[:600]
        except Exception as e: print('AI enrichment skipped',e)
    (BASE/'data.json').write_text(json.dumps(d,indent=2,ensure_ascii=False),encoding='utf-8')
if __name__=='__main__': main()
