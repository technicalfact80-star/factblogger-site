#!/usr/bin/env python3
"""Optional unattended publication path with strict structural gates.

Default behavior is DRY: creates a draft only. To publish and push, both
--enable-autopublish and --push are required. Human review remains recommended.
"""
from __future__ import annotations
import argparse, json, re, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
QUEUE=ROOT/'topic_queue.json'; STATE=ROOT/'draft_state.json'; DRAFTS=ROOT/'drafts'; POSTS=ROOT/'content'/'posts'

def count_words(post):
    bits=[post.get('title',''),post.get('excerpt',''),post.get('intro','')]
    for sec in post.get('sections',[]):
        bits.append(sec.get('heading',''))
        bits.extend(sec.get('paragraphs',[])); bits.extend(sec.get('bullets',[]))
    for faq in post.get('faqs',[]): bits += [faq.get('question',''),faq.get('answer','')]
    return len(re.findall(r"\b[\w’'-]+\b",' '.join(map(str,bits)),flags=re.UNICODE))

def main():
    ap=argparse.ArgumentParser(description='Generate the next queued draft; optional gated publish+push.')
    ap.add_argument('--enable-autopublish',action='store_true',help='Explicitly allow publication without per-article review')
    ap.add_argument('--push',action='store_true',help='Commit/push the generated post to the connected repository')
    ap.add_argument('--model',default='qwen2.5:3b')
    args=ap.parse_args()
    queue=json.loads(QUEUE.read_text(encoding='utf-8'))
    state=json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {'next_index':0}
    idx=state.get('next_index',0)
    if idx>=len(queue): print('Topic queue exhausted. Add more evergreen topics before scheduling more runs.'); return 0
    topic=queue[idx]
    start=time.time()
    cmd=[sys.executable,str(ROOT/'generate_post.py'),'--topic',topic['topic'],'--category',topic['category'],'--language',topic.get('language','en'),'--model',args.model]
    for source_url in topic.get('source_urls',[]): cmd.extend(['--source-url',source_url])
    result=subprocess.run(cmd,cwd=ROOT)
    if result.returncode: return result.returncode
    candidates=[p for p in DRAFTS.glob('*.json') if p.stat().st_mtime>=start-1]
    if not candidates: print('Draft file was not found after generation.',file=sys.stderr); return 2
    draft_path=max(candidates,key=lambda p:p.stat().st_mtime)
    post=json.loads(draft_path.read_text(encoding='utf-8'))
    words=count_words(post)
    checks={
      'substantial body (>=650 words)':words>=650,
      'at least 4 sections':len(post.get('sections',[]))>=4,
      'at least 3 FAQs':len(post.get('faqs',[]))>=3,
      'featured image source recorded':bool(post.get('image_url') and post.get('image_source_url')),
      'at least one source page retrieved and cited':len(post.get('sources',[]))>=1,
      'commercially suitable image licence reviewed by metadata':post.get('image_license') not in (None,'','Review required') and not re.search(r'non.?commercial|\bNC\b',str(post.get('image_license','')),flags=re.I),
      'title and excerpt present':bool(post.get('title') and post.get('excerpt')),
      'topic belongs to configured queue':topic.get('category')==post.get('category') and topic.get('language')==post.get('language')
    }
    failed=[label for label,passed in checks.items() if not passed]
    print('\nAutomated quality gates:')
    for label,passed in checks.items(): print(('PASS' if passed else 'FAIL')+' — '+label)
    if failed:
        print('\nNot published. Draft remains in drafts/; review or regenerate it.',file=sys.stderr)
        return 3
    if not args.enable_autopublish:
        print(f'\nDraft passed structural checks ({words} words) but remains a draft by default: {draft_path}')
        print('After reviewing the quality, try --enable-autopublish --push only if you accept the risk of publishing without human review.')
        return 0
    if not args.push:
        print('Refusing unattended publish without --push. No article has been published.',file=sys.stderr); return 4
    post['published']=True
    post.pop('ai_draft_note',None)
    target=POSTS/(re.sub(r'[^a-zA-Z0-9_-]+','-',post['slug'])+'.json')
    if target.exists(): print(f'Article slug already exists: {target}',file=sys.stderr); return 5
    POSTS.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(post,ensure_ascii=False,indent=2),encoding='utf-8')
    result=subprocess.run([sys.executable,str(ROOT/'build_site.py')],cwd=ROOT)
    if result.returncode: target.unlink(missing_ok=True); return result.returncode
    state['next_index']=idx+1
    STATE.write_text(json.dumps(state,indent=2,ensure_ascii=False),encoding='utf-8')
    try:
        subprocess.run(['git','add',str(target.relative_to(ROOT)),'public'],check=True,cwd=ROOT)
        subprocess.run(['git','commit','-m',f'Auto-publish article: {post["title"]}'],check=True,cwd=ROOT)
        subprocess.run(['git','push'],check=True,cwd=ROOT)
    except subprocess.CalledProcessError as exc:
        print(f'Git push failed: {exc}. Check repository authentication and deployment configuration.',file=sys.stderr)
        return 6
    print('Article pushed to the connected repository. Cloudflare Pages should deploy public/.')
    return 0

if __name__=='__main__': raise SystemExit(main())
