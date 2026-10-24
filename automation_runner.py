#!/usr/bin/env python3
"""Daily FactBlogger automation runner.

Default mode makes local drafts. Optional news auto-publishing is heavily gated:
2 distinct source domains, sufficient length/structure, source links and a clearly
reusable image licence. These machine checks do not prove truth or originality.
"""
from __future__ import annotations
import json, re, subprocess, sys, time
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse
import admin_server as cms

ROOT=Path(__file__).resolve().parent
CFG=ROOT/'automation_config.json'; STATE=ROOT/'automation_state.json'; DRAFTS=ROOT/'drafts'; POSTS=ROOT/'content'/'posts'
STOP={'the','and','that','this','with','from','into','what','when','where','how','why','for','are','was','were','have','has','its','about','after','before','over','under','new','latest','official','news','update','updates','india','your','their','they','will','can','you','our','use','using','all','not','more','than','will','into','a','an','of','to','in','on','is','as','by','at','or','be','it','we','its','their','for','are','and','how','when'}

def read_json(p, default):
    try: return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default
    except Exception: return default

def write_json(p, obj):
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def parse_date(value):
    if not value: return None
    try:
        dt=parsedate_to_datetime(value)
        if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        try:
            dt=datetime.fromisoformat(value.replace('Z','+00:00'))
            if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception: return None

def headline_tokens(title):
    return {x for x in re.findall(r'[a-z0-9]{3,}',str(title).lower()) if x not in STOP}

def related_sources(item, entries):
    base=headline_tokens(item.get('title',''))
    related=[]; domains=set()
    for other in entries:
        if other['url']==item['url']: continue
        d=urlparse(other['url']).netloc.lower().removeprefix('www.')
        if not d or d==urlparse(item['url']).netloc.lower().removeprefix('www.'): continue
        tok=headline_tokens(other.get('title',''))
        overlap=base & tok
        # A conservative minimum overlap to avoid treating unrelated headlines as corroboration.
        if len(overlap)>=2 and len(overlap)/max(1,min(len(base),len(tok)))>=0.35 and d not in domains:
            related.append(other); domains.add(d)
    return related

def count_words(post): return cms.post_words(post)

def image_license_safe(post):
    lic=str(post.get('image_license','')).lower()
    if not lic or 'review required' in lic or 'unknown' in lic or 'non-commercial' in lic or re.search(r'\bnc\b',lic): return False
    return any(token in lic for token in ('cc0','cc by','cc-by','public domain','publicdomain'))

def publish_guarded(post, draft_path, config):
    words=count_words(post)
    source_domains={urlparse(x.get('url','')).netloc.lower().removeprefix('www.') for x in post.get('sources',[]) if x.get('url')}
    domains={d for d in source_domains if d}
    checks={
      f"body is at least {config.get('auto_publish_min_words',700)} words": words>=int(config.get('auto_publish_min_words',700)),
      'at least 4 sections': len(post.get('sections',[]))>=4,
      'at least 3 FAQs': len(post.get('faqs',[]))>=3,
      'at least 2 cited source domains': len(domains)>=2,
      'reusable image licence metadata present': image_license_safe(post),
      'title, excerpt, introduction and description exist': all(str(post.get(k,'')).strip() for k in ('title','excerpt','intro','seo_description')),
      'News category exists': post.get('category') in [c.get('name') for c in cms.categories()]
    }
    for k,v in checks.items(): print(('PASS' if v else 'FAIL')+' — '+k)
    if not all(checks.values()):
        print(f'Guarded auto-publish withheld; draft retained: {draft_path.name}')
        return False
    post['published']=True; post['updated']=datetime.now().date().isoformat(); post.pop('ai_draft_note',None)
    target=POSTS/(re.sub(r'[^a-zA-Z0-9_\-\u0900-\u097f]+','-',str(post.get('slug','article')))+'.json')
    if target.exists():
        print(f'Publication withheld: slug already exists at {target.name}')
        return False
    POSTS.mkdir(parents=True,exist_ok=True); write_json(target,post)
    try:
        subprocess.run([sys.executable,str(ROOT/'build_site.py')],cwd=ROOT,check=True,timeout=180)
        subprocess.run(['git','add',str(target.relative_to(ROOT)),'categories.json','public'],cwd=ROOT,check=True,timeout=120)
        subprocess.run(['git','commit','-m',f'Auto-publish reviewed-gate news: {post["title"]}'],cwd=ROOT,check=True,timeout=120)
        subprocess.run(['git','push'],cwd=ROOT,check=True,timeout=180)
        draft_path.unlink(missing_ok=True)
        print(f'Published and pushed: {target.name}. Cloudflare deployment should begin.')
        return True
    except Exception as exc:
        target.unlink(missing_ok=True)
        print(f'Push/build failed; article kept as draft. Error: {exc}')
        return False

def main():
    cfg=read_json(CFG,{})
    state=read_json(STATE,{'processed_news_urls':[]})
    state.setdefault('processed_news_urls',[])
    print('=== FactBlogger daily automation ===')
    state['last_run']=datetime.now(timezone.utc).isoformat()
    if cfg.get('run_evergreen_queue_daily',True):
        if cfg.get('auto_publish_evergreen',False):
            print('\n[Evergreen] Guarded autopublish is enabled in settings.')
            cmd=[sys.executable,str(ROOT/'daily_publish.py'),'--enable-autopublish','--push']
        else:
            print('\n[Evergreen] Creating one draft from the topic queue.')
            cmd=[sys.executable,str(ROOT/'daily_draft.py')]
        try:
            result=subprocess.run(cmd,cwd=ROOT,timeout=900)
            print(f'Evergreen command exit code: {result.returncode}')
        except Exception as exc: print(f'Evergreen run failed: {exc}')
    else: print('\n[Evergreen] Disabled in settings.')
    if not cfg.get('fetch_news_daily',True):
        print('[News] RSS news automation disabled in settings.')
        write_json(STATE,state); return 0
    print('\n[News] Fetching configured RSS/Atom sources...')
    entries,errors=cms.news_items(12)
    for err in errors: print('Feed warning: '+err)
    processed=set(state['processed_news_urls'])
    max_age=int(cfg.get('max_age_hours',72)); cutoff=datetime.now(timezone.utc)-timedelta(hours=max_age)
    candidates=[]
    for item in entries:
        url=item.get('url','').split('#')[0]
        if not url or url in processed: continue
        dt=parse_date(item.get('date'))
        if dt and dt<cutoff: continue
        candidates.append(item)
    candidates=candidates[:max(1,min(10,int(cfg.get('max_news_drafts_per_run',2))))]
    print(f'Found {len(entries)} feed entries; {len(candidates)} new items selected for processing.')
    for item in candidates:
        cat=item.get('category','News & Trends')
        if cat not in [c['name'] for c in cms.categories()]: cat='News & Trends' if 'News & Trends' in [c['name'] for c in cms.categories()] else cms.categories()[0]['name']
        language=item.get('language','en') if item.get('language') in ('en','hi') else 'en'
        cmd=[sys.executable,str(ROOT/'generate_post.py'),'--topic',item['title'],'--category',cat,'--language',language]
        srcs=[item['url']]
        corroborating=related_sources(item,entries)
        if cfg.get('auto_publish_news',False) and cfg.get('require_two_source_domains_for_news_autopublish',True):
            srcs += [x['url'] for x in corroborating[:3]]
        for url in srcs: cmd.extend(['--source-url',url])
        before={p.resolve() for p in DRAFTS.glob('*.json')} if DRAFTS.exists() else set()
        print(f"\nGenerating: {item['title']} [{item.get('source_name','')}]" )
        try: result=subprocess.run(cmd,cwd=ROOT,timeout=480)
        except Exception as exc:
            print(f'Generation failed: {exc}'); continue
        if result.returncode:
            print(f"Generation failed for: {item['title']}; item will be retried next run."); continue
        fresh=[p for p in DRAFTS.glob('*.json') if p.resolve() not in before]
        if not fresh:
            print('No new draft file found; item will be retried next run.'); continue
        draft_path=max(fresh,key=lambda p:p.stat().st_mtime)
        post=read_json(draft_path,{})
        post['news_metadata']={'source_url':item['url'],'headline':item['title'],'source_name':item.get('source_name'),'source_date':item.get('date'),'corroborating_headlines':[{'title':x['title'],'url':x['url']} for x in corroborating[:3]],'review_required':True}
        write_json(draft_path,post)
        published=False
        if cfg.get('auto_publish_news',False):
            published=publish_guarded(post,draft_path,cfg)
        if not published:
            print(f'Draft ready for review: {draft_path.name}')
        processed.add(item['url'].split('#')[0])
        state['processed_news_urls']=list(processed)[-5000:]
        state['last_news_run']=datetime.now(timezone.utc).isoformat()
        write_json(STATE,state)
    write_json(STATE,state)
    print('\nAutomation finished. Check drafts/ and logs/; no unverified article was guaranteed to publish.')
    return 0

if __name__=='__main__': raise SystemExit(main())
