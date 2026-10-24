#!/usr/bin/env python3
"""Promote a reviewed draft into the published content library; optional explicit git push."""
from __future__ import annotations
import argparse, json, re, shutil, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DRAFTS=ROOT/'drafts'; POSTS=ROOT/'content'/'posts'

def main():
    ap=argparse.ArgumentParser(description='Publish a reviewed AI draft to the local site.')
    ap.add_argument('draft',help='Draft filename in drafts/, or its path')
    ap.add_argument('--push',action='store_true',help='After review/promotion and build, git commit and push changes to trigger deployment')
    args=ap.parse_args()
    src=Path(args.draft)
    if not src.is_absolute(): src=DRAFTS/src
    if not src.exists(): print(f'Draft not found: {src}',file=sys.stderr); return 2
    try: post=json.loads(src.read_text(encoding='utf-8'))
    except Exception as exc: print(f'Invalid JSON: {exc}',file=sys.stderr); return 2
    required=['slug','title','excerpt','language','category','seo_description','intro','sections']
    missing=[key for key in required if not post.get(key)]
    if missing: print('Missing required fields: '+', '.join(missing),file=sys.stderr); return 2
    if post.get('language') not in ('en','hi'): print('language must be en or hi',file=sys.stderr); return 2
    if not isinstance(post.get('sections'),list) or len(post['sections'])<3: print('Add at least three substantive sections before publishing.',file=sys.stderr); return 2
    if not post.get('image_url'): print('Add a suitable featured image or explicitly document why the article does not need one.',file=sys.stderr); return 2
    if post.get('image_license') == 'Review required': print('Image licence needs to be verified. Replace the fallback image or verify its terms and record the licence before publishing.',file=sys.stderr); return 2
    print('\nREVIEW CHECKLIST — do not publish unless all are true:')
    for item in ['I checked factual claims and dates against reliable sources.','I opened and verified every source link.','I reviewed image relevance, licence, credit and alt text.','The article is original, useful, well-edited and not repetitive.','The chosen category and language are correct.']:
        print(' [ ] '+item)
    answer=input('\nHave you completed every check and want to publish this draft locally? Type PUBLISH to confirm: ').strip()
    if answer!='PUBLISH': print('Cancelled. Draft remains unchanged.'); return 1
    post['published']=True
    post.pop('ai_draft_note',None)
    POSTS.mkdir(parents=True,exist_ok=True)
    target=POSTS/(re.sub(r'[^a-zA-Z0-9_-]+','-',post['slug'])+'.json')
    if target.exists(): print(f'An article already exists at {target}',file=sys.stderr); return 2
    target.write_text(json.dumps(post,ensure_ascii=False,indent=2),encoding='utf-8')
    subprocess.run([sys.executable,str(ROOT/'build_site.py')],check=True,cwd=ROOT)
    print(f'Published locally: {target}\nPreview the site with start_preview.bat before pushing online.')
    if args.push:
        try:
            subprocess.run(['git','add',str(target.relative_to(ROOT)),'public'],check=True,cwd=ROOT)
            subprocess.run(['git','commit','-m',f'Publish article: {post["title"]}'],check=True,cwd=ROOT)
            subprocess.run(['git','push'],check=True,cwd=ROOT)
            print('Pushed to GitHub; connected Cloudflare Pages should deploy the new article.')
        except subprocess.CalledProcessError as exc:
            print(f'Git push did not complete: {exc}. The article is still published locally.',file=sys.stderr); return 3
    return 0

if __name__=='__main__': raise SystemExit(main())
