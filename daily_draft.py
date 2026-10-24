#!/usr/bin/env python3
"""Create the next review-first draft from topic_queue.json. Does not publish it."""
import json, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
QUEUE=ROOT/'topic_queue.json'; STATE=ROOT/'draft_state.json'

def main():
    topics=json.loads(QUEUE.read_text(encoding='utf-8'))
    state=json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {'next_index':0}
    idx=state.get('next_index',0)
    if idx>=len(topics):
        print('Topic queue is complete. Add new verified topic ideas to topic_queue.json before continuing.'); return 0
    item=topics[idx]
    cmd=[sys.executable,str(ROOT/'generate_post.py'),'--topic',item['topic'],'--category',item['category'],'--language',item.get('language','en')]
    for source_url in item.get('source_urls',[]): cmd.extend(['--source-url',source_url])
    print('Creating review-first draft:',item['topic'])
    result=subprocess.run(cmd,cwd=ROOT)
    if result.returncode==0:
        state['next_index']=idx+1
        STATE.write_text(json.dumps(state,indent=2,ensure_ascii=False),encoding='utf-8')
    return result.returncode
if __name__=='__main__': raise SystemExit(main())
