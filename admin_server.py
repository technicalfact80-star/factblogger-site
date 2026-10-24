#!/usr/bin/env python3
"""FactBlogger local admin CMS (Python standard library only).

Binds only to 127.0.0.1. Do not expose this admin server to the public Internet.
"""
from __future__ import annotations
import html, json, os, re, subprocess, sys, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / 'site_config.json'
CATEGORIES_PATH = ROOT / 'categories.json'
SOURCES_PATH = ROOT / 'news_sources.json'
AUTOMATION_PATH = ROOT / 'automation_config.json'
STATE_PATH = ROOT / 'automation_state.json'
NEWS_CACHE_PATH = ROOT / 'news_cache.json'
POSTS = ROOT / 'content' / 'posts'
DRAFTS = ROOT / 'drafts'
HOST, PORT = '127.0.0.1', int(os.environ.get('FACTBLOGGER_ADMIN_PORT', '8787'))

DEFAULT_CATEGORIES = [
    {'name':'AI & Technology','slug':'ai-technology','icon':'✳','short':'AI tools, software, coding and technology tutorials.','description':'Practical AI and technology guides, software explainers, coding workflows and digital safety tips.'},
    {'name':'Education & Careers','slug':'education-careers','icon':'↗','short':'Internships, resumes, courses and career guides.','description':'Useful resources for students, freshers, job seekers, portfolios and software career preparation.'},
    {'name':'Blogging & SEO','slug':'blogging-seo','icon':'⌁','short':'Search, content, websites and growth.','description':'Clear guides to search engine optimization, content planning, site structure and website publishing.'},
    {'name':'Apps & Software','slug':'apps-software','icon':'▦','short':'App tutorials, reviews and software solutions.','description':'App settings, troubleshooting, software comparisons and practical product guides.'},
    {'name':'India Digital Guides','slug':'india-digital-guides','icon':'⌘','short':'Online services and digital life in India.','description':'Digital safety, online services and practical technology explanations for readers in India.'},
    {'name':'News & Trends','slug':'news-trends','icon':'◉','short':'Verified technology news, official announcements and explainers.','description':'Carefully sourced updates about technology, AI and digital developments, with primary-source links.'}
]

def read_json(path, default):
    if not path.exists(): return default
    try: return json.loads(path.read_text(encoding='utf-8'))
    except Exception: return default

def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    tmp.replace(path)

def categories():
    cats=read_json(CATEGORIES_PATH, DEFAULT_CATEGORIES)
    return cats if isinstance(cats,list) and cats else DEFAULT_CATEGORIES

def slugify(text):
    s=str(text or '').strip().lower()
    s=re.sub(r'[^a-z0-9\u0900-\u097f]+','-',s)
    return re.sub(r'-+','-',s).strip('-')[:90] or 'article'

def esc(x): return html.escape(str(x or ''), quote=True)
def text_plain(s): return re.sub(r'\s+',' ',re.sub(r'<[^>]*>',' ',str(s or ''))).strip()
def source_urls(lines):
    out=[]
    for raw in (lines or '').splitlines():
        u=raw.strip()
        if not u: continue
        parsed=urlparse(u)
        if parsed.scheme=='https' and parsed.netloc:
            out.append({'title':parsed.netloc,'url':u})
    return out

def sections_to_markdown(sections):
    out=[]
    for sec in sections or []:
        out.append('## '+str(sec.get('heading') or 'Section'))
        out.extend(str(p) for p in sec.get('paragraphs',[]) if p)
        for bullet in sec.get('bullets',[]) or []: out.append('- '+str(bullet))
        out.append('')
    return '\n\n'.join(out).strip()

def markdown_to_sections(body):
    sections=[]; current={'heading':'Overview','paragraphs':[],'bullets':[]}; para=[]
    def flush_para():
        nonlocal para
        if para:
            current['paragraphs'].append(' '.join(para).strip()); para=[]
    def flush_section():
        flush_para()
        if current['paragraphs'] or current['bullets']:
            sections.append(current.copy())
    for line in (body or '').splitlines():
        line=line.rstrip()
        if line.startswith('## '):
            flush_section(); current={'heading':line[3:].strip(),'paragraphs':[],'bullets':[]}
        elif re.match(r'^\s*[-*]\s+',line):
            flush_para(); current['bullets'].append(re.sub(r'^\s*[-*]\s+','',line).strip())
        elif not line.strip(): flush_para()
        else: para.append(line.strip())
    flush_section()
    return [s for s in sections if s['heading'] and (s['paragraphs'] or s['bullets'])]

def post_words(post):
    txt=[post.get('title',''),post.get('excerpt',''),post.get('intro','')]
    for sec in post.get('sections',[]):
        txt.append(sec.get('heading','')); txt += sec.get('paragraphs',[]); txt += sec.get('bullets',[])
    for faq in post.get('faqs',[]): txt += [faq.get('question',''),faq.get('answer','')]
    return len(re.findall(r"\b[\w’'-]+\b",' '.join(str(x) for x in txt),flags=re.UNICODE))

def safe_file_name(name):
    name=Path(str(name or '')).name
    if not re.fullmatch(r'[A-Za-z0-9_\-\u0900-\u097f]+\.json',name): return None
    return name

def list_posts():
    items=[]
    for folder,kind in [(POSTS,'published'),(DRAFTS,'draft')]:
        if not folder.exists(): continue
        for path in folder.glob('*.json'):
            try: p=json.loads(path.read_text(encoding='utf-8'))
            except Exception: continue
            p['_kind']=kind; p['_file']=path.name; p['_mtime']=path.stat().st_mtime
            items.append(p)
    items.sort(key=lambda p:p.get('_mtime',0), reverse=True)
    return items

def read_feed(url, timeout=12):
    u=urlparse(url)
    if u.scheme!='https' or not u.netloc: raise ValueError('Only HTTPS RSS/Atom source URLs are allowed.')
    req=urllib.request.Request(url, headers={'User-Agent':'FactBloggerNewsBot/1.0 (+source attribution; contact site owner)','Accept':'application/rss+xml, application/atom+xml, application/xml, text/xml, */*'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw=r.read(2_500_000)
        if r.status >= 400: raise ValueError(f'HTTP {r.status}')
    root=ET.fromstring(raw)
    entries=[]
    # RSS 2.0
    for item in root.findall('.//item'):
        title=text_plain(item.findtext('title',''))
        link=(item.findtext('link','') or '').strip()
        desc=text_plain(item.findtext('description',''))
        pub=(item.findtext('pubDate','') or item.findtext('{http://purl.org/dc/elements/1.1/}date','')).strip()
        guid=(item.findtext('guid','') or link).strip()
        if title and link and urlparse(link).scheme=='https': entries.append({'title':title,'url':link,'description':desc[:1200],'date':pub,'id':guid})
    # Atom feeds
    ns={'a':'http://www.w3.org/2005/Atom'}
    if not entries:
        for entry in root.findall('.//a:entry',ns):
            title=text_plain(entry.findtext('a:title','',ns))
            link=''
            for link_el in entry.findall('a:link',ns):
                if link_el.attrib.get('rel','alternate')=='alternate': link=link_el.attrib.get('href',''); break
            desc=text_plain(entry.findtext('a:summary','',ns) or entry.findtext('a:content','',ns))
            pub=(entry.findtext('a:published','',ns) or entry.findtext('a:updated','',ns)).strip()
            if title and link and urlparse(link).scheme=='https': entries.append({'title':title,'url':link,'description':desc[:1200],'date':pub,'id':link})
    return entries

def ollama_available():
    try:
        return subprocess.run(['ollama','--version'],capture_output=True,timeout=3).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False

def news_items(max_per_source=10):
    result=[]; errors=[]
    for src in read_json(SOURCES_PATH,[]):
        if not src.get('enabled',True): continue
        try:
            entries=read_feed(src.get('url',''))
            for item in entries[:max_per_source]:
                item.update({'source_name':src.get('name','News source'),'source_url':src.get('url',''),'source_domain':src.get('domain') or urlparse(item['url']).netloc,'category':src.get('category','News & Trends'),'language':src.get('language','en'),'trust_level':src.get('trust_level','review')})
                result.append(item)
        except Exception as exc: errors.append(f"{src.get('name','Source')}: {exc}")
    # Dedupe by canonical article URL, keep feed order and sort by feed date if parseable
    unique=[]; seen=set()
    for it in result:
        key=it['url'].split('#')[0]
        if key in seen: continue
        seen.add(key); unique.append(it)
    return unique, errors

def render_page(title, content, notice=''):
    config=read_json(CONFIG_PATH,{})
    site=config.get('site_name','FactBlogger')
    nav='''<nav><a href="/">Dashboard</a><a href="/posts">Posts</a><a href="/post/new">New article</a><a href="/categories">Categories</a><a href="/topics">Topic queue</a><a href="/news">Latest news</a><a href="/sources">News sources</a><a href="/settings">Automation settings</a></nav>'''
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)} — {esc(site)} Admin</title><style>
:root{{color-scheme:light;--ink:#172033;--muted:#64748b;--line:#dce3ee;--brand:#1959a6;--bg:#f5f7fb;--card:#fff;--green:#12784a;--amber:#986400}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,-apple-system,Segoe UI,sans-serif}}header{{background:#10243b;color:#fff;padding:19px max(20px,calc((100vw - 1120px)/2))}}header strong{{font-size:20px}}header small{{color:#c8d4e5;display:block}}nav{{display:flex;flex-wrap:wrap;gap:8px;padding:14px max(20px,calc((100vw - 1120px)/2));background:#fff;border-bottom:1px solid var(--line)}}nav a{{text-decoration:none;color:var(--brand);padding:8px 10px;border:1px solid var(--line);border-radius:9px;font-weight:650}}main{{max-width:1120px;margin:24px auto;padding:0 18px 60px}}h1{{font-size:30px;line-height:1.15;margin:0 0 8px}}h2{{font-size:19px;margin:6px 0 14px}}.muted{{color:var(--muted)}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:13px;margin:20px 0}}.card,.panel{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:17px;box-shadow:0 2px 8px #13233a07}}.kpi{{font-size:28px;font-weight:800}}.grid2{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}}label{{display:block;font-weight:700;margin:12px 0 5px}}input,textarea,select{{font:inherit;width:100%;border:1px solid #cbd5e1;border-radius:8px;padding:10px 11px;background:white;color:var(--ink)}}textarea{{min-height:120px;resize:vertical}}textarea.long{{min-height:280px}}.help{{font-size:13px;color:var(--muted);margin-top:4px}}.btn,button{{display:inline-block;background:var(--brand);color:white;text-decoration:none;border:0;border-radius:8px;padding:10px 14px;font:inherit;font-weight:700;cursor:pointer}}.btn.secondary,button.secondary{{background:#eef4fb;color:var(--brand);border:1px solid #c8d8ef}}.btn.danger,button.danger{{background:#fff0f0;color:#9c2727;border:1px solid #ffcaca}}.actions{{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:15px}}table{{width:100%;border-collapse:collapse;background:white}}th,td{{text-align:left;padding:10px;border-bottom:1px solid var(--line);vertical-align:top}}th{{font-size:12px;text-transform:uppercase;color:var(--muted)}}td form{{display:inline}}.pill{{display:inline-block;padding:3px 8px;background:#e9f5ee;color:var(--green);border-radius:999px;font-size:12px;font-weight:800}}.pill.warn{{background:#fff4d6;color:var(--amber)}}.notice{{padding:12px 14px;background:#eaf3ff;border:1px solid #cfe2ff;border-radius:10px;margin:14px 0}}.error{{background:#fff0f0;border-color:#ffcaca}}.empty{{padding:25px;text-align:center;color:var(--muted)}}.headline{{padding:15px 0;border-bottom:1px solid var(--line)}}.headline h3{{font-size:17px;margin:0 0 5px}}.headline p{{margin:6px 0;color:var(--muted)}}.headline .meta{{font-size:12px;color:var(--muted)}}.inline{{display:inline-block;width:auto}}.danger-text{{color:#9c2727}}.mono{{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;overflow-wrap:anywhere}}footer{{max-width:1120px;margin:auto;padding:20px;color:var(--muted);font-size:12px}}
</style></head><body><header><strong>FactBlogger — Local Admin Studio</strong><small>Local-only control panel. It is not part of the public website.</small></header>{nav}<main>{('<div class="notice">'+esc(notice)+'</div>') if notice else ''}{content}</main><footer>Admin runs only on this computer at 127.0.0.1. Do not port-forward or expose this server publicly. Always verify news, facts, copyright and image licensing before publication.</footer></body></html>'''

class Handler(BaseHTTPRequestHandler):
    server_version = 'FactBloggerAdmin/1.0'
    def log_message(self, fmt, *args): print('[admin]', fmt % args)
    def send_html(self, body, status=200):
        raw=body.encode('utf-8'); self.send_response(status); self.send_header('Content-Type','text/html; charset=utf-8'); self.send_header('Content-Length',str(len(raw))); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(raw)
    def redirect(self, path): self.send_response(303); self.send_header('Location',path); self.end_headers()
    def parse_form(self):
        n=int(self.headers.get('Content-Length','0') or 0)
        if n>3_000_000: raise ValueError('Form too large (3 MB maximum).')
        raw=self.rfile.read(n).decode('utf-8','replace')
        parsed=urllib.parse.parse_qs(raw,keep_blank_values=True)
        return {k:v[-1] for k,v in parsed.items()}
    def guard_local_post(self):
        host=self.headers.get('Host','').split(':')[0].lower()
        if host not in ('127.0.0.1','localhost'): return False
        origin=self.headers.get('Origin')
        if origin:
            parsed=urlparse(origin)
            if parsed.hostname not in ('127.0.0.1','localhost'): return False
        return True
    def do_GET(self):
        try:
            return self._do_GET_inner()
        except Exception as exc:
            return self.send_html(render_page('Request failed',f'<h1>Request failed</h1><div class="notice error">{esc(type(exc).__name__)}: {esc(exc)}</div><p><a href="/">Return to dashboard</a></p>'),500)
    def _do_GET_inner(self):
        u=urllib.parse.urlparse(self.path); path=u.path; qs=urllib.parse.parse_qs(u.query)
        if path=='/': return self.dashboard(qs.get('notice',[''])[0])
        if path=='/categories': return self.categories_page(qs.get('notice',[''])[0])
        if path=='/topics': return self.topics_page(qs.get('notice',[''])[0])
        if path=='/posts': return self.posts_page(qs.get('notice',[''])[0])
        if path=='/post/new': return self.post_editor(None,'draft','')
        if path=='/post/edit': return self.post_editor(qs.get('file',[''])[0],qs.get('kind',['draft'])[0],qs.get('notice',[''])[0])
        if path=='/news': return self.news_page(qs.get('notice',[''])[0])
        if path=='/sources': return self.sources_page(qs.get('notice',[''])[0])
        if path=='/settings': return self.settings_page(qs.get('notice',[''])[0])
        return self.send_html(render_page('Not found','<h1>Not found</h1><p><a href="/">Return to dashboard</a></p>'),404)
    def do_POST(self):
        if not self.guard_local_post(): return self.send_html(render_page('Blocked','<h1>Request blocked</h1><p>Admin accepts requests from this computer only.</p>'),403)
        try: form=self.parse_form()
        except Exception as exc: return self.send_html(render_page('Bad request',f'<h1>Bad request</h1><p>{esc(exc)}</p>'),400)
        path=urllib.parse.urlparse(self.path).path
        handlers={'/category/save':self.save_category,'/category/delete':self.delete_category,'/topics/save':self.save_topic,'/topics/delete':self.delete_topic,'/site/build':self.build_site_action,'/post/save':self.save_post,'/post/delete':self.delete_post,'/ai/generate':self.ai_generate,'/news/draft':self.news_draft,'/news/refresh':self.news_refresh,'/sources/save':self.save_sources,'/settings/save':self.save_settings,'/automation/run':self.run_automation}
        fn=handlers.get(path)
        if not fn: return self.send_html(render_page('Not found','<h1>Action not found</h1>'),404)
        try: fn(form)
        except Exception as exc:
            self.send_html(render_page('Action failed',f'<h1>Action failed</h1><div class="notice error">{esc(type(exc).__name__)}: {esc(exc)}</div><p>Check the terminal window for more detail.</p><p><a href="/">Return to admin</a></p>'),500)
    def dashboard(self,notice=''):
        allp=list_posts(); published=sum(1 for p in allp if p['_kind']=='published'); drafts=len(allp)-published
        cats=categories(); state=read_json(STATE_PATH,{'processed_news_urls':[]})
        content=f'''<h1>Admin dashboard</h1><p class="muted">Create and manage posts, add categories, discover current headlines and run local AI automation.</p>
<div class="cards"><div class="card"><div class="muted">Published articles</div><div class="kpi">{published}</div></div><div class="card"><div class="muted">Drafts</div><div class="kpi">{drafts}</div></div><div class="card"><div class="muted">Categories</div><div class="kpi">{len(cats)}</div></div><div class="card"><div class="muted">Processed news links</div><div class="kpi">{len(state.get('processed_news_urls',[]))}</div></div></div>
<div class="grid2"><section class="panel"><h2>Quick actions</h2><div class="actions"><a class="btn" href="/post/new">Write article manually</a><a class="btn secondary" href="/categories">Manage categories</a><a class="btn secondary" href="/news">Fetch latest news</a></div><form action="/site/build" method="post"><label><input class="inline" style="width:auto" type="checkbox" name="push" value="yes"> Build and push live site now</label><button class="secondary">Rebuild website</button></form><p class="help">Manual edits and AI-generated drafts save to local JSON files. Publishing rebuilds the static website; Git push triggers deployment when your repository is connected.</p></section>
<section class="panel"><h2>Automation status</h2><p>Local AI: {('<span class="pill">Ollama installed</span>' if ollama_available() else '<span class="pill warn">Check Ollama installation</span>')}</p><p>Website URL: <span class="mono">{esc(read_json(CONFIG_PATH,{}).get('base_url','not configured'))}</span></p><p class="help">Automation runs only when this PC is awake, connected to the internet, and Ollama is available.</p><form method="post" action="/automation/run"><button>Run daily automation now</button></form></section></div>
<section class="panel" style="margin-top:16px"><h2>Recently edited</h2>{self.post_table(allp[:8])}</section>'''
        self.send_html(render_page('Dashboard',content,notice))
    def post_table(self, posts):
        if not posts: return '<div class="empty">No posts found.</div>'
        rows=''.join(f'''<tr><td><strong>{esc(p.get('title','Untitled'))}</strong><div class="help">{esc(p.get('slug',''))}</div></td><td>{esc(p.get('category',''))}</td><td>{esc(p.get('language','en'))}</td><td><span class="pill {'warn' if p['_kind']=='draft' else ''}">{p['_kind']}</span></td><td><a class="btn secondary" href="/post/edit?kind={p['_kind']}&file={urllib.parse.quote(p['_file'])}">Edit</a></td></tr>''' for p in posts)
        return f'<div style="overflow-x:auto"><table><thead><tr><th>Title / slug</th><th>Category</th><th>Language</th><th>Status</th><th>Action</th></tr></thead><tbody>{rows}</tbody></table></div>'
    def posts_page(self,notice=''):
        items=list_posts(); content=f'<h1>Articles and drafts</h1><p class="muted">Edit existing posts or create a new article. Published articles are rebuilt into static pages.</p><div class="actions"><a class="btn" href="/post/new">+ New article</a></div><section class="panel" style="margin-top:16px">{self.post_table(items)}</section>'
        self.send_html(render_page('Posts',content,notice))
    def categories_page(self,notice=''):
        cats=categories(); rows=''
        for c in cats:
            rows+=f'''<tr><td><strong>{esc(c['name'])}</strong><div class="help">/{esc(c['slug'])}/</div></td><td>{esc(c.get('description',''))}</td><td><button class="secondary" type="button" data-cat="{esc(json.dumps(c,ensure_ascii=False))}" onclick="fillCat(JSON.parse(this.dataset.cat))">Edit</button><form method="post" action="/category/delete" onsubmit="return confirm('Delete this category? Posts in this category prevent deletion.')"><input type="hidden" name="slug" value="{esc(c['slug'])}"><label class="inline"><input class="inline" style="width:auto" type="checkbox" name="push" value="yes"> Push</label><button class="danger">Delete</button></form></td></tr>'''
        form='''<section class="panel"><h2 id="cat-title">Add category</h2><form action="/category/save" method="post"><input type="hidden" id="old_slug" name="old_slug" value=""><label>Category name *</label><input id="cat_name" name="name" required placeholder="e.g. AI & Technology"><label>URL slug *</label><input id="cat_slug" name="slug" required placeholder="ai-technology" pattern="[a-z0-9]+(-[a-z0-9]+)*"><p class="help">Use English lowercase letters, numbers and hyphens only. Slugs become permanent category URLs.</p><label>Icon (emoji or symbol)</label><input id="cat_icon" name="icon" maxlength="8" value="•"><label>Short description</label><input id="cat_short" name="short" maxlength="180"><label>Full description</label><textarea id="cat_description" name="description" required></textarea><label><input class="inline" style="width:auto" type="checkbox" name="push" value="yes"> Also push category changes to live website</label><div class="actions"><button>Save category</button><button type="button" class="secondary" onclick="resetCat()">Clear form</button></div></form></section>
<script>function fillCat(c){document.getElementById('cat-title').innerText='Edit category';document.getElementById('old_slug').value=c.slug;for(const k of ['name','slug','icon','short','description'])document.getElementById('cat_'+k).value=c[k]||'';window.scrollTo({top:0,behavior:'smooth'})}function resetCat(){document.getElementById('cat-title').innerText='Add category';document.getElementById('old_slug').value='';for(const k of ['name','slug','short','description'])document.getElementById('cat_'+k).value='';document.getElementById('cat_icon').value='•'}</script>'''
        content=f'<h1>Categories</h1><p class="muted">Add, edit or delete categories. Changes are saved to categories.json and reflected after rebuilding the site.</p><div class="grid2">{form}<section class="panel"><h2>Current categories ({len(cats)})</h2><div style="overflow-x:auto"><table><thead><tr><th>Name / URL</th><th>Description</th><th>Actions</th></tr></thead><tbody>{rows}</tbody></table></div></section></div>'
        self.send_html(render_page('Categories',content,notice))
    def save_category(self,f):
        name=f.get('name','').strip(); slug=slugify(f.get('slug') or name); old=f.get('old_slug','').strip()
        if not name or not slug: raise ValueError('Category name and slug are required.')
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',slug): raise ValueError('Slug must use lowercase Latin letters, numbers and hyphens.')
        cats=categories()
        if any(c['slug']==slug and c['slug']!=old for c in cats): raise ValueError('That category URL slug already exists.')
        if any(c['name'].casefold()==name.casefold() and c['slug']!=old for c in cats): raise ValueError('That category name already exists.')
        item={'name':name,'slug':slug,'icon':f.get('icon','•').strip()[:8] or '•','short':f.get('short','').strip() or f.get('description','').strip(),'description':f.get('description','').strip() or f.get('short','').strip() or name}
        if old:
            found=False
            for c in cats:
                if c['slug']==old:
                    old_name=c['name']; c.update(item); found=True
                    if old_name!=name:
                        self.update_category_references(old_name,name)
                    break
            if not found: raise ValueError('Category to edit was not found.')
        else: cats.append(item)
        write_json(CATEGORIES_PATH,cats)
        subprocess.run([sys.executable,str(ROOT/'build_site.py')],cwd=ROOT,check=True,timeout=180)
        if f.get('push')=='yes':
            paths=['categories.json','public','content/posts','topic_queue.json','news_sources.json']
            if DRAFTS.exists() and list(DRAFTS.glob('*.json')): paths.append('drafts')
            self.git_push(paths, 'Update FactBlogger categories')
            self.redirect('/categories?notice='+urllib.parse.quote('Category saved, site rebuilt and pushed. Cloudflare deployment should start.'))
        else:
            self.redirect('/categories?notice='+urllib.parse.quote('Category saved and local site rebuilt. Use Rebuild website on the dashboard with the push option to deploy live.'))
    def update_category_references(self, old_name, new_name):
        for folder in (POSTS,DRAFTS):
            if folder.exists():
                for p in folder.glob('*.json'):
                    try: data=json.loads(p.read_text(encoding='utf-8'))
                    except Exception: continue
                    if data.get('category')==old_name: data['category']=new_name; write_json(p,data)
        for path, is_list in ((SOURCES_PATH, True), (ROOT/'topic_queue.json', True)):
            items=read_json(path,[])
            changed=False
            if isinstance(items,list):
                for item in items:
                    if isinstance(item,dict) and item.get('category')==old_name:
                        item['category']=new_name; changed=True
            if changed: write_json(path,items)
    def delete_category(self,f):
        slug=f.get('slug',''); cats=categories(); target=next((c for c in cats if c['slug']==slug),None)
        if not target: raise ValueError('Category not found.')
        used=[]
        for folder in (POSTS,DRAFTS):
            if folder.exists():
                for p in folder.glob('*.json'):
                    data=read_json(p,{})
                    if data.get('category')==target['name']: used.append(p.name)
        if used: raise ValueError('Category is used by posts/drafts; move those articles first: '+', '.join(used[:5]))
        queue=[x for x in read_json(ROOT/'topic_queue.json',[]) if isinstance(x,dict) and x.get('category')==target['name']]
        sources=[x for x in read_json(SOURCES_PATH,[]) if isinstance(x,dict) and x.get('category')==target['name']]
        if queue or sources: raise ValueError('Category is still used by the evergreen topic queue or news sources. Update those entries first.')
        if len(cats)<=1: raise ValueError('At least one category must remain.')
        write_json(CATEGORIES_PATH,[c for c in cats if c['slug']!=slug])
        subprocess.run([sys.executable,str(ROOT/'build_site.py')],cwd=ROOT,check=True,timeout=180)
        if f.get('push')=='yes':
            paths=['categories.json','public','content/posts','topic_queue.json','news_sources.json']
            if DRAFTS.exists() and list(DRAFTS.glob('*.json')): paths.append('drafts')
            self.git_push(paths, 'Remove FactBlogger category')
        self.redirect('/categories?notice='+urllib.parse.quote('Category deleted and site rebuilt.' + (' Pushed to live deployment.' if f.get('push')=='yes' else ' Tick Push on a category delete or use Dashboard to deploy live.')))
    def post_editor(self, filename, kind='draft', notice=''):
        is_new=not filename
        post={}
        if not is_new:
            safe=safe_file_name(filename)
            if not safe: raise ValueError('Invalid filename.')
            folder=DRAFTS if kind=='draft' else POSTS
            post_path=folder/safe
            if not post_path.exists(): raise ValueError('Post file not found.')
            post=read_json(post_path,{})
        cats=categories(); cat_opts=''.join(f'<option value="{esc(c["name"])}" {"selected" if c["name"]==post.get("category",cats[0]["name"]) else ""}>{esc(c["name"])}</option>' for c in cats)
        src_lines='\n'.join(x.get('url','') for x in post.get('sources',[]))
        body=sections_to_markdown(post.get('sections',[]))
        tags=', '.join(post.get('tags',[]))
        content=f'''<h1>{'New article' if is_new else 'Edit article'}</h1><p class="muted">Write manually or use the AI form below. Save drafts freely; publishing rebuilds the static website.</p>
<section class="panel"><form action="/post/save" method="post"><input type="hidden" name="original_file" value="{esc(filename or '')}"><input type="hidden" name="original_kind" value="{esc(kind)}"><label>Title *</label><input name="title" required maxlength="180" value="{esc(post.get('title',''))}"><label>URL slug *</label><input name="slug" required pattern="[a-z0-9\u0900-\u097f]+(-[a-z0-9\u0900-\u097f]+)*" value="{esc(post.get('slug',''))}" placeholder="how-to-use-ai-tools"><label>Category *</label><select name="category">{cat_opts}</select><div class="grid2"><div><label>Language *</label><select name="language"><option value="en" {'selected' if post.get('language','en')=='en' else ''}>English</option><option value="hi" {'selected' if post.get('language')=='hi' else ''}>Hindi</option></select></div><div><label>Author</label><input name="author" value="{esc(post.get('author','FactBlogger Editorial Team'))}"></div></div><label>Short excerpt *</label><textarea name="excerpt" required>{esc(post.get('excerpt',''))}</textarea><label>SEO description</label><input name="seo_description" maxlength="180" value="{esc(post.get('seo_description',''))}"><label>Introduction *</label><textarea name="intro" required>{esc(post.get('intro',''))}</textarea><label>Article body (Markdown-style)</label><textarea class="long" name="body" placeholder="## First section\nParagraph text...\n\n## Second section\nMore detail...">{esc(body)}</textarea><p class="help">Use headings beginning with ##. Use blank lines between paragraphs. Use - at line start for bullets. Aim for 3+ useful sections.</p><label>FAQs (one per line: question :: answer)</label><textarea name="faqs">{esc(chr(10).join(str(x.get('question',''))+' :: '+str(x.get('answer','')) for x in post.get('faqs',[])))}</textarea><label>Tags (comma-separated)</label><input name="tags" value="{esc(tags)}"><div class="grid2"><div><label>Featured image URL (https)</label><input name="image_url" type="url" value="{esc(post.get('image_url',''))}"><label>Image alt text</label><input name="image_alt" value="{esc(post.get('image_alt',''))}"></div><div><label>Image credit</label><input name="image_credit" value="{esc(post.get('image_credit',''))}"><label>Image licence</label><input name="image_license" value="{esc(post.get('image_license',''))}"></div></div><label>Image source URL</label><input name="image_source_url" type="url" value="{esc(post.get('image_source_url',''))}"><label>Image licence URL</label><input name="image_license_url" type="url" value="{esc(post.get('image_license_url',''))}"><label>Source URLs (one HTTPS URL per line)</label><textarea name="sources">{esc(src_lines)}</textarea><div class="notice">Publishing checks required fields, unique slug, source/image metadata and section count. These checks cannot guarantee factual accuracy or AdSense approval.</div><div class="actions"><button name="intent" value="draft">Save draft</button><button name="intent" value="publish">Publish locally</button><label class="inline"><input class="inline" style="width:auto" type="checkbox" name="push" value="yes"> Also push to GitHub / live deploy</label></div></form></section>
<section class="panel" style="margin-top:16px"><h2>Generate an AI draft</h2><p class="muted">Ollama must be installed and running. The generated result is saved as a draft, not automatically published by this action.</p><form action="/ai/generate" method="post"><label>Topic or news headline</label><input name="topic" required placeholder="e.g. What a new AI feature means for Indian students"><label>Category</label><select name="category">{cat_opts}</select><label>Language</label><select name="language"><option value="en">English</option><option value="hi">Hindi</option></select><label>Source URLs (one per line, HTTPS only)</label><textarea name="sources" placeholder="https://official-source.example/news/article"></textarea><div class="actions"><button>Generate AI draft</button></div></form></section>'''
        self.send_html(render_page('Article editor',content,notice))
    def save_post(self,f):
        title=f.get('title','').strip(); category=f.get('category','').strip(); lang=f.get('language','en').strip(); slug=slugify(f.get('slug') or title)
        cat_names=[c['name'] for c in categories()]
        if not title or category not in cat_names: raise ValueError('Title and a currently configured category are required.')
        if lang not in ('en','hi'): raise ValueError('Language must be English or Hindi.')
        body=markdown_to_sections(f.get('body',''))
        faqs=[]
        for line in f.get('faqs','').splitlines():
            if '::' in line:
                q,a=line.split('::',1)
                if q.strip() and a.strip(): faqs.append({'question':q.strip(),'answer':a.strip()})
        srcs=source_urls(f.get('sources',''))
        post={'slug':slug,'title':title,'excerpt':f.get('excerpt','').strip(),'seo_description':f.get('seo_description','').strip(),'intro':f.get('intro','').strip(),'sections':body,'faqs':faqs,'tags':[x.strip() for x in f.get('tags','').split(',') if x.strip()],'sources':srcs,'language':lang,'category':category,'author':f.get('author','FactBlogger Editorial Team').strip() or 'FactBlogger Editorial Team','published':False,'date':datetime.now().date().isoformat(),'updated':datetime.now().date().isoformat(),'image_url':f.get('image_url','').strip(),'image_alt':f.get('image_alt','').strip(),'image_credit':f.get('image_credit','').strip(),'image_source_url':f.get('image_source_url','').strip(),'image_license':f.get('image_license','').strip(),'image_license_url':f.get('image_license_url','').strip(),'read_minutes':max(1,round(post_words({'title':title,'excerpt':f.get('excerpt',''),'intro':f.get('intro',''),'sections':body})/200))}
        if not re.fullmatch(r'[a-z0-9\u0900-\u097f]+(?:-[a-z0-9\u0900-\u097f]+)*',slug): raise ValueError('Slug may use lowercase English letters, Hindi letters, numbers and hyphens.')
        old_file=f.get('original_file',''); old_kind=f.get('original_kind','draft')
        if old_file:
            safe=safe_file_name(old_file)
            source=(DRAFTS if old_kind=='draft' else POSTS)/safe
            if not safe or not source.exists(): raise ValueError('Original post file not found.')
            original_data=read_json(source,{})
            post['date']=original_data.get('date',post['date'])
            if original_data.get('updated'): post['updated']=datetime.now().date().isoformat()
            if slug+'.json' != source.name and (POSTS/(slug+'.json')).exists(): raise ValueError('Slug conflicts with an existing published post.')
        else:
            if (DRAFTS/(slug+'.json')).exists() or (POSTS/(slug+'.json')).exists(): raise ValueError('That slug is already used by an article or draft. Choose a unique URL slug.')
        if f.get('intent')=='publish':
            issues=[]
            if len(body)<3: issues.append('add at least 3 substantive sections')
            if not post['image_url'].startswith('https://'): issues.append('add a valid HTTPS featured image URL')
            if not post['image_source_url'].startswith('https://'): issues.append('add an image source URL')
            if not post['image_license_url'].startswith('https://'): issues.append('add an image licence URL')
            if not post['image_alt'].strip(): issues.append('add descriptive image alt text')
            if not post['image_license'] or 'review required' in post['image_license'].lower() or 'unknown' in post['image_license'].lower(): issues.append('verify and record the image licence')
            if not post['excerpt'] or not post['intro']: issues.append('add excerpt and introduction')
            if issues: raise ValueError('Cannot publish yet: '+ '; '.join(issues)+'.')
            post['published']=True
            target=POSTS/(slug+'.json'); target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists() and not (old_kind=='published' and old_file==target.name):
                raise ValueError('A published post already uses this slug. Choose a different slug or edit the existing article.')
            write_json(target,post)
            if old_file and old_kind=='draft': (DRAFTS/safe).unlink(missing_ok=True)
            self.build_and_optionally_push(f, target, f'Publish article: {title}')
            return
        DRAFTS.mkdir(parents=True,exist_ok=True); target=DRAFTS/(slug+'.json')
        if old_file and old_kind=='draft':
            safe=safe_file_name(old_file)
            if safe and (DRAFTS/safe).exists() and safe!=target.name: (DRAFTS/safe).unlink()
        write_json(target,post)
        self.redirect('/post/edit?kind=draft&file='+urllib.parse.quote(target.name)+'&notice='+urllib.parse.quote('Draft saved locally.'))
    def build_and_optionally_push(self,f, target, message):
        subprocess.run([sys.executable,str(ROOT/'build_site.py')],cwd=ROOT,check=True,timeout=180)
        # Re-run the existing preflight if present; warnings may not indicate a hard failure.
        if f.get('push')=='yes':
            self.git_push([str(target.relative_to(ROOT)),'categories.json','public'], message)
            self.redirect('/posts?notice='+urllib.parse.quote('Article built and pushed. Cloudflare deployment should start automatically.'))
        else: self.redirect('/posts?notice='+urllib.parse.quote('Article published to local site build. Preview it, then push to deploy online.'))
    def git_push(self, paths, message):
        subprocess.run(['git','add',*paths],cwd=ROOT,check=True,timeout=120)
        diff=subprocess.run(['git','diff','--cached','--quiet'],cwd=ROOT,timeout=30)
        if diff.returncode == 1:
            subprocess.run(['git','commit','-m',message],cwd=ROOT,check=True,timeout=120)
        elif diff.returncode > 1:
            raise RuntimeError('Could not inspect staged Git changes.')
        subprocess.run(['git','push'],cwd=ROOT,check=True,timeout=180)
    def build_site_action(self,f):
        subprocess.run([sys.executable,str(ROOT/'build_site.py')],cwd=ROOT,check=True,timeout=180)
        if f.get('push')=='yes':
            self.git_push(['categories.json','public'], 'Rebuild FactBlogger site')
            self.redirect('/?notice='+urllib.parse.quote('Site rebuilt and pushed to GitHub; wait for the Cloudflare deployment to finish.'))
        else:
            self.redirect('/?notice='+urllib.parse.quote('Local static site rebuilt. Check preview; tick push to deploy online.'))
    def topics_page(self,notice=''):
        queue=read_json(ROOT/'topic_queue.json',[])
        cats=''.join(f'<option value="{esc(c["name"])}">{esc(c["name"])}</option>' for c in categories())
        rows=''.join(f'''<tr><td>{i+1}</td><td><strong>{esc(t.get('topic'))}</strong><div class="help">{esc(', '.join(t.get('source_urls',[])))}</div></td><td>{esc(t.get('category'))}</td><td>{esc(t.get('language','en'))}</td><td><form action="/topics/delete" method="post" onsubmit="return confirm('Delete this queued topic? The saved queue index may need resetting if you remove an earlier item.')"><input type="hidden" name="index" value="{i}"><button class="danger">Delete</button></form></td></tr>''' for i,t in enumerate(queue))
        content=f'''<h1>Evergreen topic queue</h1><p class="muted">Add ideas the scheduled AI workflow can turn into drafts. One queue item becomes one article draft per run. Sources are one HTTPS URL per line.</p><section class="panel"><h2>Add a topic</h2><form action="/topics/save" method="post"><label>Topic / reader question *</label><input name="topic" required maxlength="220" placeholder="How to choose a secure password manager"><label>Category *</label><select name="category">{cats}</select><label>Language</label><select name="language"><option value="en">English</option><option value="hi">Hindi</option></select><label>Trusted source URLs</label><textarea name="sources" placeholder="https://official-source.example/docs"></textarea><button>Add to queue</button></form></section><section class="panel" style="margin-top:16px"><h2>Queued topics ({len(queue)})</h2><div style="overflow-x:auto"><table><thead><tr><th>#</th><th>Topic and sources</th><th>Category</th><th>Lang</th><th>Action</th></tr></thead><tbody>{rows}</tbody></table></div><p class="help">If you delete an item before the current draft_state.json index, open Settings/Queue reset guidance in the setup guide. Queue topics are ideas, not verified facts.</p></section>'''
        self.send_html(render_page('Topic queue',content,notice))
    def save_topic(self,f):
        topic=f.get('topic','').strip(); category=f.get('category','').strip(); language=f.get('language','en').strip()
        if not topic: raise ValueError('Topic is required.')
        if category not in [c['name'] for c in categories()]: raise ValueError('Choose an existing category.')
        if language not in ('en','hi'): raise ValueError('Language must be en or hi.')
        queue=read_json(ROOT/'topic_queue.json',[])
        queue.append({'topic':topic,'category':category,'language':language,'source_urls':[x['url'] for x in source_urls(f.get('sources',''))]})
        write_json(ROOT/'topic_queue.json',queue)
        self.redirect('/topics?notice='+urllib.parse.quote('Topic added to the end of the queue.'))
    def delete_topic(self,f):
        queue=read_json(ROOT/'topic_queue.json',[])
        try: index=int(f.get('index','-1'))
        except Exception: raise ValueError('Invalid queue item index.')
        if index<0 or index>=len(queue): raise ValueError('Topic was not found.')
        queue.pop(index); write_json(ROOT/'topic_queue.json',queue)
        self.redirect('/topics?notice='+urllib.parse.quote('Topic removed. If the daily queue reports an exhausted/offset issue, check draft_state.json per the guide.'))
    def delete_post(self,f):
        kind=f.get('kind','draft'); safe=safe_file_name(f.get('file',''))
        if not safe: raise ValueError('Invalid file name.')
        path=(DRAFTS if kind=='draft' else POSTS)/safe
        if not path.exists(): raise ValueError('Post not found.')
        if kind=='published': raise ValueError('For safety, published posts are not deleted here. Edit/unpublish through the source JSON and rebuild, or use the repository backup first.')
        path.unlink(); self.redirect('/posts?notice='+urllib.parse.quote('Draft deleted.'))
    def ai_generate(self,f):
        topic=f.get('topic','').strip(); category=f.get('category','').strip(); language=f.get('language','en').strip()
        if not topic: raise ValueError('Enter an article topic.')
        if category not in [c['name'] for c in categories()]: raise ValueError('Select a valid category.')
        cmd=[sys.executable,str(ROOT/'generate_post.py'),'--topic',topic,'--category',category,'--language',language]
        for s in source_urls(f.get('sources','')): cmd += ['--source-url',s['url']]
        before={p.resolve() for p in DRAFTS.glob('*.json')} if DRAFTS.exists() else set()
        proc=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=420,encoding='utf-8',errors='replace')
        if proc.returncode:
            msg=(proc.stderr or proc.stdout or 'AI generation failed')[-2400:]
            return self.send_html(render_page('AI generation failed',f'<h1>AI generation failed</h1><pre>{esc(msg)}</pre><p>Check that Ollama is installed and running, then try again.</p><p><a href="/post/new">Back to editor</a></p>'),500)
        candidates=[p for p in DRAFTS.glob('*.json') if p.resolve() not in before]
        if not candidates: candidates=sorted(DRAFTS.glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:1]
        if not candidates: raise RuntimeError('No draft file was produced. See output: '+proc.stdout[-1000:])
        target=max(candidates,key=lambda p:p.stat().st_mtime)
        self.redirect('/post/edit?kind=draft&file='+urllib.parse.quote(target.name)+'&notice='+urllib.parse.quote('AI draft created. Review claims, sources and image licence before publishing.'))
    def news_page(self,notice=''):
        cache=read_json(NEWS_CACHE_PATH,{'entries':[],'errors':[],'fetched_at':None})
        entries=cache.get('entries',[]); errors=cache.get('errors',[])
        state=read_json(STATE_PATH,{'processed_news_urls':[]}); processed=set(state.get('processed_news_urls',[]))
        errors_html=('<div class="notice error"><strong>Some feeds failed:</strong><br>'+ '<br>'.join(esc(x) for x in errors)+'</div>') if errors else ''
        cards=''
        for item in entries:
            card_id=item['url']
            badge='<span class="pill">Processed</span>' if card_id in processed else '<span class="pill warn">New</span>'
            cards+=f'''<article class="headline"><div class="meta">{esc(item.get('source_name'))} · {esc(item.get('date'))} · {esc(item.get('trust_level'))} {badge}</div><h3><a href="{esc(item['url'])}" target="_blank" rel="noopener noreferrer">{esc(item['title'])}</a></h3><p>{esc(item.get('description','')[:450])}</p><form action="/news/draft" method="post"><input type="hidden" name="topic" value="{esc(item['title'])}"><input type="hidden" name="source_url" value="{esc(item['url'])}"><input type="hidden" name="category" value="{esc(item.get('category','News & Trends'))}"><input type="hidden" name="language" value="{esc(item.get('language','en'))}"><button {'disabled' if card_id in processed else ''}>Create AI draft from this headline</button></form></article>'''
        if not entries: cards='<div class="empty">No feed items fetched. Check source URLs and internet connection in the News Sources page.</div>'
        content=f'''<h1>Latest news monitor</h1><p class="muted">Fetch headline metadata from configured RSS/Atom sources. We use headline, dates and the original link as research input; do not copy source articles wholesale.</p><div class="actions"><form action="/news/refresh" method="post"><button>Refresh feeds</button></form><a class="btn secondary" href="/sources">Manage sources</a></div><p class="help">Last refresh: {esc(cache.get('fetched_at') or 'never')}. The page uses a saved feed cache so it loads quickly.</p>{errors_html}<section class="panel" style="margin-top:16px"><h2>Current feed headlines ({len(entries)})</h2>{cards}</section>'''
        self.send_html(render_page('Latest news',content,notice))
    def news_refresh(self,f):
        entries, errors = news_items(8)
        write_json(NEWS_CACHE_PATH, {'entries': entries, 'errors': errors, 'fetched_at': datetime.now(timezone.utc).isoformat()})
        self.redirect('/news?notice='+urllib.parse.quote(f'Feed refresh completed: {len(entries)} unique headlines; {len(errors)} source error(s).'))
    def news_draft(self,f):
        topic=f.get('topic','').strip(); url=f.get('source_url','').strip(); category=f.get('category','News & Trends').strip(); lang=f.get('language','en').strip()
        if not topic or urlparse(url).scheme!='https': raise ValueError('Headline and HTTPS source URL required.')
        if category not in [c['name'] for c in categories()]: category='News & Trends' if 'News & Trends' in [c['name'] for c in categories()] else categories()[0]['name']
        cmd=[sys.executable,str(ROOT/'generate_post.py'),'--topic',topic,'--category',category,'--language',lang,'--source-url',url]
        before={p.resolve() for p in DRAFTS.glob('*.json')} if DRAFTS.exists() else set()
        proc=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=420,encoding='utf-8',errors='replace')
        if proc.returncode: raise RuntimeError('Could not create draft: '+(proc.stderr or proc.stdout)[-1800:])
        candidates=[p for p in DRAFTS.glob('*.json') if p.resolve() not in before]
        if candidates:
            target=max(candidates,key=lambda p:p.stat().st_mtime)
            post=read_json(target,{})
            post['news_metadata']={'source_url':url,'headline':topic,'fetched_at':datetime.now(timezone.utc).isoformat(),'review_required':True}
            write_json(target,post)
            # Mark source item processed once a draft has been successfully made.
            state=read_json(STATE_PATH,{'processed_news_urls':[]}); urls=state.setdefault('processed_news_urls',[])
            if url not in urls: urls.append(url)
            state['processed_news_urls']=urls[-5000:]; write_json(STATE_PATH,state)
            return self.redirect('/post/edit?kind=draft&file='+urllib.parse.quote(target.name)+'&notice='+urllib.parse.quote('News article draft created. Verify publication date, facts and source context before publishing.'))
        raise RuntimeError('Generator completed but did not create a draft.')
    def sources_page(self,notice=''):
        srcs=read_json(SOURCES_PATH,[])
        rows=''.join(f'''<tr><td>{esc(s.get('name'))}<div class="help">{esc(s.get('domain'))} · {esc(s.get('trust_level'))}</div></td><td class="mono">{esc(s.get('url'))}</td><td>{'Enabled' if s.get('enabled',True) else 'Disabled'}</td></tr>''' for s in srcs)
        cats=''.join(f'<option>{esc(c["name"])}</option>' for c in categories())
        content=f'''<h1>News source configuration</h1><p class="muted">Only add sources you trust and have permission to reference. The system stores headlines/link metadata; the AI should create a new explanation with attribution, not republish article text.</p><section class="panel"><h2>Configured sources ({len(srcs)})</h2><div style="overflow-x:auto"><table><thead><tr><th>Source</th><th>RSS/Atom URL</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table></div></section><section class="panel" style="margin-top:16px"><h2>Add or replace sources</h2><form action="/sources/save" method="post"><label>Sources JSON</label><textarea class="long" name="sources_json">{esc(json.dumps(srcs,ensure_ascii=False,indent=2))}</textarea><p class="help">Expected fields: name, url (HTTPS feed URL), domain, category, language (en/hi), enabled (true/false), trust_level. Save the entire JSON array.</p><button>Save sources</button></form></section>'''
        self.send_html(render_page('News sources',content,notice))
    def save_sources(self,f):
        try: srcs=json.loads(f.get('sources_json',''))
        except Exception as exc: raise ValueError('Invalid JSON: '+str(exc))
        if not isinstance(srcs,list): raise ValueError('Sources must be a JSON list.')
        for s in srcs:
            if not isinstance(s,dict) or not s.get('name') or urlparse(s.get('url','')).scheme!='https': raise ValueError('Every source needs a name and an HTTPS feed URL.')
            if s.get('category') not in [c['name'] for c in categories()]: raise ValueError('Each source category must exist in categories.json.')
            if s.get('language','en') not in ('en','hi'): raise ValueError('Source language must be en or hi.')
        write_json(SOURCES_PATH,srcs); self.redirect('/sources?notice='+urllib.parse.quote('News sources saved.'))
    def settings_page(self,notice=''):
        cfg=read_json(AUTOMATION_PATH,{})
        def ck(k): return 'checked' if cfg.get(k,False) else ''
        content=f'''<h1>Automation settings</h1><p class="muted">Changes apply to future local runs. This control panel cannot run while your PC is powered off.</p><section class="panel"><form action="/settings/save" method="post"><label><input class="inline" style="width:auto" type="checkbox" name="run_evergreen_queue_daily" value="true" {ck('run_evergreen_queue_daily')}> Generate one evergreen draft from topic_queue.json daily</label><label><input class="inline" style="width:auto" type="checkbox" name="fetch_news_daily" value="true" {ck('fetch_news_daily')}> Fetch news feeds and create new drafts daily</label><label>Maximum new news drafts per daily run</label><input type="number" min="1" max="10" name="max_news_drafts_per_run" value="{int(cfg.get('max_news_drafts_per_run',2))}"><label><input class="inline" style="width:auto" type="checkbox" name="auto_publish_news" value="true" {ck('auto_publish_news')}> Enable guarded news auto-publishing (advanced; not recommended until tested)</label><label><input class="inline" style="width:auto" type="checkbox" name="auto_publish_evergreen" value="true" {ck('auto_publish_evergreen')}> Enable gated evergreen auto-publishing from topic queue</label><label>Minimum article word count for any auto-publication</label><input type="number" min="500" max="3000" name="auto_publish_min_words" value="{int(cfg.get('auto_publish_min_words',700))}"><div class="notice error"><strong>Risk note:</strong> auto-publishing can publish inaccurate or thin articles despite automated checks. News auto-publishing will require at least two independent source domains and licence-clean image metadata. Search ranking and AdSense approval are never guaranteed.</div><button>Save automation settings</button></form></section><section class="panel" style="margin-top:16px"><h2>Run now</h2><p>Creates drafts from the configured news feeds and/or evergreen queue, according to the settings.</p><form action="/automation/run" method="post"><button>Run automation now</button></form></section>'''
        self.send_html(render_page('Automation settings',content,notice))
    def save_settings(self,f):
        old=read_json(AUTOMATION_PATH,{})
        cfg={
            'run_evergreen_queue_daily':f.get('run_evergreen_queue_daily')=='true',
            'fetch_news_daily':f.get('fetch_news_daily')=='true',
            'max_news_drafts_per_run':max(1,min(10,int(f.get('max_news_drafts_per_run','2')))),
            'auto_publish_news':f.get('auto_publish_news')=='true',
            'auto_publish_evergreen':f.get('auto_publish_evergreen')=='true',
            'max_age_hours':int(old.get('max_age_hours',72)),
            'require_two_source_domains_for_news_autopublish':True,
            'auto_publish_min_words':max(500,min(3000,int(f.get('auto_publish_min_words','700')))),
            'schedule_note':old.get('schedule_note','Windows Task Scheduler runs run_daily_automation.bat. Keep the PC awake and Ollama running.')
        }
        write_json(AUTOMATION_PATH,cfg); self.redirect('/settings?notice='+urllib.parse.quote('Automation settings saved.'))
    def run_automation(self,f):
        proc=subprocess.run([sys.executable,str(ROOT/'automation_runner.py')],cwd=ROOT,capture_output=True,text=True,timeout=1800,encoding='utf-8',errors='replace')
        out=(proc.stdout or '')+'\n'+(proc.stderr or '')
        content=f'<h1>Automation result</h1><p class="muted">Exit code: {proc.returncode}</p><section class="panel"><pre style="white-space:pre-wrap;overflow-wrap:anywhere">{esc(out[-10000:])}</pre></section><p><a class="btn" href="/posts">View drafts and articles</a> <a class="btn secondary" href="/">Dashboard</a></p>'
        self.send_html(render_page('Automation result',content),200 if proc.returncode==0 else 500)


def main():
    if not CATEGORIES_PATH.exists(): write_json(CATEGORIES_PATH,DEFAULT_CATEGORIES)
    if not SOURCES_PATH.exists(): write_json(SOURCES_PATH,[])
    if not AUTOMATION_PATH.exists(): write_json(AUTOMATION_PATH,{})
    server=ThreadingHTTPServer((HOST,PORT),Handler)
    print(f'FactBlogger Local Admin is running at http://{HOST}:{PORT}')
    print('This dashboard is local-only. Keep this terminal open. Press Ctrl+C to stop.')
    try: server.serve_forever()
    except KeyboardInterrupt: print('\nAdmin stopped.')
    finally: server.server_close()

if __name__=='__main__': main()
