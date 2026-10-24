#!/usr/bin/env python3
"""Local preflight audit for FactBlogger's static site and launch readiness.
This checks technical integrity, not Google rankings or AdSense approval.
"""
from __future__ import annotations
import json, re, sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, unquote

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / 'public'
CONFIG = json.loads((ROOT / 'site_config.json').read_text(encoding='utf-8'))
POSTS = ROOT / 'content' / 'posts'

class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.hrefs=[]; self.srcs=[]; self.title=''; self.in_title=False; self.meta={}; self.canonical=''; self.lang=''
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag=='a' and a.get('href'): self.hrefs.append(a['href'])
        if tag in ('img','script') and a.get('src'): self.srcs.append(a['src'])
        if tag=='title': self.in_title=True
        if tag=='html': self.lang=a.get('lang','')
        if tag=='meta' and a.get('name'): self.meta[a['name'].lower()]=a.get('content','')
        if tag=='link' and a.get('rel','').lower()=='canonical': self.canonical=a.get('href','')
    def handle_endtag(self, tag):
        if tag=='title': self.in_title=False
    def handle_data(self, data):
        if self.in_title: self.title += data

def words(post):
    bits=[post.get('title',''),post.get('excerpt',''),post.get('intro','')]
    for sec in post.get('sections',[]):
        bits.append(sec.get('heading','')); bits.extend(sec.get('paragraphs',[])); bits.extend(sec.get('bullets',[]))
    for faq in post.get('faqs',[]): bits.extend([faq.get('question',''),faq.get('answer','')])
    return len(re.findall(r'\S+', ' '.join(map(str,bits))))

def local_path(url, source_html):
    parsed=urlsplit(url)
    if parsed.scheme or parsed.netloc or url.startswith(('#','mailto:','tel:','javascript:','data:')): return None
    path=unquote(parsed.path or '')
    if not path: return None
    if path.startswith('/'):
        rel=path.lstrip('/')
    else:
        rel=str((source_html.parent / path).relative_to(PUBLIC))
    target=PUBLIC / rel
    if path.endswith('/') or target.is_dir(): target=target/'index.html'
    elif not target.suffix: target=target/'index.html'
    return target

def main():
    blockers=[]; warnings=[]; passed=[]
    def ok(msg): passed.append(msg)
    def warn(msg): warnings.append(msg)
    def block(msg): blockers.append(msg)

    if CONFIG.get('site_name')=='FactBlogger': ok('Site branding set to FactBlogger')
    else: block('site_config.json site_name must be FactBlogger')
    base=str(CONFIG.get('base_url','')).strip()
    base_ok=base.startswith('https://') and 'YOUR-' not in base and re.fullmatch(r'https://[A-Za-z0-9.-]+(?::\d+)?/', base) is not None
    if base_ok: ok('HTTPS base URL configured')
    else: block('Set base_url to the exact live HTTPS site origin with a trailing slash (example: https://project.pages.dev/)')
    email=str(CONFIG.get('contact_email','')).strip()
    if re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+',email) and 'REPLACE_WITH' not in email: ok('Contact email configured')
    else: block('Replace contact_email with an email address you control')
    if CONFIG.get('google_site_verification'): ok('Search Console verification token configured')
    else: warn('Google Search Console verification token not configured yet; add it after selecting a verification method')
    pub=str(CONFIG.get('adsense_publisher_id','')).strip()
    if pub and not re.fullmatch(r'ca-pub-\d{16}',pub): block('AdSense publisher ID format is invalid; use only the ID shown in your AdSense account')
    elif not pub: warn('AdSense is not connected; this is expected before applying or receiving a publisher ID')
    else: ok('AdSense publisher ID format is valid')

    categories_path=ROOT/'categories.json'
    category_list=[]
    if categories_path.exists():
        try:
            category_list=json.loads(categories_path.read_text(encoding='utf-8'))
            if not isinstance(category_list,list) or not category_list: block('categories.json must be a non-empty JSON array')
            else: ok(f'{len(category_list)} configurable categories found')
        except Exception as exc: block(f'categories.json is invalid: {exc}')
    else: warn('categories.json is missing; builder will use built-in categories')
    required=['index.html','404.html','categories/index.html','about/index.html','contact/index.html','privacy-policy/index.html','disclaimer/index.html','editorial-policy/index.html','robots.txt','sitemap.xml','rss.xml']
    missing=[f for f in required if not (PUBLIC/f).exists()]
    if missing: block('Generated public files missing: '+', '.join(missing))
    else: ok('Homepage, 404, policy pages, robots, sitemap and RSS exist')

    content_posts=[]
    for path in sorted(POSTS.glob('*.json')):
        try: post=json.loads(path.read_text(encoding='utf-8'))
        except Exception as exc: block(f'{path.name}: invalid JSON ({exc})'); continue
        if post.get('published'): content_posts.append((path,post))
    if len(content_posts)>=5: ok(f'{len(content_posts)} starter articles marked published in source library')
    else: warn(f'Only {len(content_posts)} published source articles. This is not an official AdSense minimum; focus on genuinely useful topic coverage and depth.')
    for path,post in content_posts:
        w=words(post)
        if w<500: warn(f'{path.name}: about {w} words; check whether the topic is answered in enough depth (no official minimum word count)')
        if not post.get('sources'): warn(f'{path.name}: no source links; add sources for claims that need verification')
        if not post.get('image_alt'): warn(f'{path.name}: featured image needs meaningful alt text')
        if post.get('image_url') and post.get('image_credit') and not post.get('image_license_url'):
            warn(f'{path.name}: check the image licence and attribution requirements manually')
    if content_posts: ok('Content library JSON is readable')

    if PUBLIC.exists():
        html_files=[]
        for candidate in PUBLIC.rglob('*.html'):
            if candidate.name.startswith('google') and 'google-site-verification:' in candidate.read_text(encoding='utf-8',errors='replace')[:300]:
                continue
            html_files.append(candidate)
        for cat in category_list:
            slug=str(cat.get('slug','')) if isinstance(cat,dict) else ''
            if slug and not (PUBLIC/'categories'/slug/'index.html').exists(): block(f'Missing generated page for category slug: {slug}')
        broken=[]; html_no_title=[]; old_brand=[]
        for p in html_files:
            raw=p.read_text(encoding='utf-8',errors='replace')
            if '<title>' not in raw: html_no_title.append(str(p.relative_to(PUBLIC)))
            if 'DigitalDisha' in raw or '>DD</span>' in raw: old_brand.append(str(p.relative_to(PUBLIC)))
            parser=Links(); parser.feed(raw)
            for u in parser.hrefs+parser.srcs:
                dest=local_path(u,p)
                if dest is not None and not dest.exists(): broken.append(f'{p.relative_to(PUBLIC)} -> {u}')
        if broken: block('Broken local links/assets: '+ '; '.join(broken[:12]))
        else: ok(f'No broken local links/assets found across {len(html_files)} HTML files')
        if html_no_title: block('HTML page missing title: '+', '.join(html_no_title[:10]))
        else: ok('Every generated HTML page has a title')
        if old_brand: block('Old DigitalDisha branding remains in: '+', '.join(old_brand[:10]))
        else: ok('Generated pages use FactBlogger branding')
        try:
            sm=(PUBLIC/'sitemap.xml').read_text(encoding='utf-8')
            if base_ok and '<loc>'+base not in sm: warn('Sitemap may not include the configured origin; rebuild after setting base_url')
            if base_ok and '<loc>https://' in sm: ok('Sitemap contains absolute HTTPS URLs')
            elif not base_ok: warn('Sitemap is intentionally empty until the live base_url is configured')
        except Exception as exc: block(f'Cannot read sitemap.xml: {exc}')
    else: block('public/ directory does not exist; run py build_site.py')

    print('FACTBLOGGER LOCAL PREFLIGHT')
    print('='*72)
    for msg in passed: print('PASS  '+msg)
    for msg in warnings: print('WARN  '+msg)
    for msg in blockers: print('BLOCK '+msg)
    print('-'*72)
    print(f'Result: {len(passed)} passed, {len(warnings)} warnings, {len(blockers)} blockers')
    print('This is a technical preflight only; it cannot predict Google indexing, ranking, or AdSense approval.')
    return 1 if blockers else 0

if __name__=='__main__': raise SystemExit(main())
