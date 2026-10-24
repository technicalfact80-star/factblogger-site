#!/usr/bin/env python3
"""Build a fast, SEO-friendly static FactBlogger site using only Python stdlib."""
from __future__ import annotations
import html, json, os, re, shutil, stat, time
from pathlib import Path
from datetime import date, datetime
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / 'content' / 'posts'
PUBLIC = ROOT / 'public'
ASSETS = ROOT / 'assets'
CONFIG = json.loads((ROOT / 'site_config.json').read_text(encoding='utf-8'))
SITE = CONFIG.get('site_name', 'FactBlogger')
BASE = CONFIG.get('base_url', '').strip()
BASE = BASE.rstrip('/') + '/' if BASE else ''
BASE_OK = bool(re.fullmatch(r'https://[A-Za-z0-9.-]+(?::[0-9]+)?/', BASE)) and 'YOUR-' not in BASE
EMAIL = CONFIG.get('contact_email', '').strip()
DEFAULT_CATEGORIES = [
    {'name':'AI & Technology','slug':'ai-technology','icon':'✳','short':'AI tools, software, coding and technology tutorials.','description':'Practical AI and technology guides, software explainers, coding workflows and digital safety tips.'},
    {'name':'Education & Careers','slug':'education-careers','icon':'↗','short':'Internships, resumes, courses and career guides.','description':'Useful resources for students, freshers, job seekers, portfolios and software career preparation.'},
    {'name':'Blogging & SEO','slug':'blogging-seo','icon':'⌁','short':'Search, content, websites and growth.','description':'Clear guides to search engine optimization, content planning, site structure and website publishing.'},
    {'name':'Apps & Software','slug':'apps-software','icon':'▦','short':'App tutorials, reviews and software solutions.','description':'App settings, troubleshooting, software comparisons and practical product guides.'},
    {'name':'India Digital Guides','slug':'india-digital-guides','icon':'⌘','short':'Online services and digital life in India.','description':'Digital safety, online services and practical technology explanations for readers in India.'},
    {'name':'News & Trends','slug':'news-trends','icon':'◉','short':'Verified technology news, official announcements and useful explainers.','description':'Carefully sourced updates about technology, AI and important digital developments, with context and links to primary sources.'}
]

def load_categories():
    path = ROOT / 'categories.json'
    try:
        raw = json.loads(path.read_text(encoding='utf-8')) if path.exists() else DEFAULT_CATEGORIES
    except Exception as exc:
        print(f'WARNING: cannot read categories.json ({exc}); using built-in categories')
        raw = DEFAULT_CATEGORIES
    if not isinstance(raw, list):
        raise ValueError('categories.json must contain a JSON array')
    categories = []
    seen_names, seen_slugs = set(), set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get('name', '')).strip()
        slug = str(item.get('slug', '')).strip().lower()
        if not name or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug):
            continue
        if name.casefold() in seen_names or slug in seen_slugs:
            continue
        category = {
            'name': name, 'slug': slug,
            'icon': str(item.get('icon', '•'))[:8],
            'short': str(item.get('short') or item.get('description') or name),
            'description': str(item.get('description') or item.get('short') or name)
        }
        categories.append(category)
        seen_names.add(name.casefold()); seen_slugs.add(slug)
    if not categories:
        raise ValueError('categories.json contains no valid categories')
    return categories

CATEGORIES = load_categories()
CAT_MAP = {c['name']: c for c in CATEGORIES}


def esc(value): return html.escape(str(value or ''), quote=True)
def date_iso(value):
    try: return date.fromisoformat(value).isoformat()
    except Exception: return date.today().isoformat()
def date_human(value, lang='en'):
    try:
        d = date.fromisoformat(value)
        return d.strftime('%d %b %Y')
    except Exception: return value or ''
def slugify(value):
    value = str(value or '').lower().strip()
    value = re.sub(r'[^a-z0-9\u0900-\u097f]+', '-', value)
    value = re.sub(r'-+', '-', value).strip('-')
    return value or 'article'
def site_url(path=''):
    return BASE + path.lstrip('/') if BASE_OK else '/' + path.lstrip('/')

def load_posts():
    posts=[]
    CONTENT.mkdir(parents=True, exist_ok=True)
    for path in sorted(CONTENT.glob('*.json')):
        try: post=json.loads(path.read_text(encoding='utf-8'))
        except Exception as e:
            print(f'WARNING: skipping invalid JSON {path.name}: {e}'); continue
        if not post.get('published', False): continue
        if post.get('category') not in CAT_MAP:
            print(f'WARNING: {path.name} has unknown category {post.get("category")!r}; skipped'); continue
        slug = str(post.get('slug') or '')
        if not slug or not post.get('title'):
            print(f'WARNING: {path.name} is missing slug/title; skipped'); continue
        # Slugs become filesystem paths. Only allow URL-safe Latin/Devanagari characters and hyphens.
        if not re.fullmatch(r'[a-z0-9\u0900-\u097f]+(?:-[a-z0-9\u0900-\u097f]+)*', slug):
            print(f'WARNING: {path.name} has unsafe slug {slug!r}; skipped'); continue
        if post.get('language') not in ('en', 'hi'):
            print(f'WARNING: {path.name} has unsupported language {post.get("language")!r}; skipped'); continue
        if not isinstance(post.get('sections'), list) or not post.get('sections'):
            print(f'WARNING: {path.name} has no article sections; skipped'); continue
        post['_path']=path
        posts.append(post)
    seen = set()
    unique_posts = []
    for post in posts:
        if post['slug'] in seen:
            print(f'WARNING: duplicate article slug {post["slug"]!r}; skipping {post["_path"].name}')
            continue
        seen.add(post['slug'])
        unique_posts.append(post)
    unique_posts.sort(key=lambda p: (p.get('date',''), p.get('title','')), reverse=True)
    return unique_posts

def nav_html(active=''):
    items=[('Home','/'), *[(c['name'],f"/categories/{c['slug']}/") for c in CATEGORIES]]
    links=''.join(f'<a href="{esc(href)}" class="{"active" if active==label else ""}">{esc(label)}</a>' for label,href in items[:4])
    # Keep the main nav compact on desktop; all categories remain available from homepage and category directory.
    return links + '<a href="/about/">About</a><a class="nav-cta" href="/categories/">Explore topics ↗</a>'

def head(title, description, path='', lang='en', image='', article=None):
    canonical = site_url(path) if BASE_OK else ''
    meta_canonical = f'<link rel="canonical" href="{esc(canonical)}">' if canonical else ''
    meta_robots = '<meta name="robots" content="noindex,follow">' if path == '404.html' else ('<meta name="robots" content="index,follow,max-image-preview:large">' if BASE_OK else '<meta name="robots" content="noindex,nofollow">')
    share_img = image or (site_url('assets/og-cover.svg') if BASE_OK else '/assets/og-cover.svg')
    lang_tag = 'hi-IN' if lang=='hi' else 'en-IN'
    ads = ''
    verification = str(CONFIG.get('google_site_verification', '')).strip()
    verification_meta = f'<meta name="google-site-verification" content="{esc(verification)}">' if re.fullmatch(r'[A-Za-z0-9_-]{10,200}', verification) else ''
    pub = CONFIG.get('adsense_publisher_id','').strip()
    if CONFIG.get('adsense_auto_ads_enabled') and re.fullmatch(r'ca-pub-\d{16}', pub):
        ads = f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={esc(pub)}" crossorigin="anonymous"></script>'
    og_type='article' if article else 'website'
    schema=''
    if path == '' and BASE_OK:
        website_schema = {
          '@context':'https://schema.org','@type':'WebSite','name':SITE,
          'url':BASE,'description':CONFIG.get('description',''),
          'inLanguage':['en-IN','hi-IN'],
          'publisher':{'@type':'Organization','name':SITE,'url':BASE,'logo':{'@type':'ImageObject','url':site_url('assets/og-cover.svg')}}
        }
        schema = '<script type="application/ld+json">' + json.dumps(website_schema, ensure_ascii=False).replace('</','<\\/') + '</script>'
    if article:
        article_url=site_url(path)
        schema_obj={
          '@context':'https://schema.org','@type':'Article','headline':article.get('title',''),
          'description':article.get('seo_description') or article.get('excerpt',''),
          'datePublished':date_iso(article.get('date','')),
          'dateModified':date_iso(article.get('updated') or article.get('date','')),
          'author':{'@type':'Organization','name':article.get('author') or SITE},
          'publisher':{'@type':'Organization','name':SITE}
        }
        if BASE_OK: schema_obj['mainEntityOfPage']={'@type':'WebPage','@id':article_url}
        if image: schema_obj['image']=[image]
        schema='<script type="application/ld+json">'+json.dumps(schema_obj,ensure_ascii=False).replace('</','<\\/')+'</script>'
    return f'''<!doctype html>
<html lang="{lang_tag}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title><meta name="description" content="{esc(description)}">{meta_robots}{meta_canonical}
<meta name="theme-color" content="#17213f"><meta property="og:site_name" content="{esc(SITE)}"><meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(description)}"><meta property="og:type" content="{og_type}"><meta property="og:image" content="{esc(share_img)}"><meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{esc(title)}"><meta name="twitter:description" content="{esc(description)}">
<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="/assets/styles.css">{verification_meta}{ads}{schema}</head>'''

def header(active=''):
    return f'''<div class="topline"><div class="wrap"><span><i class="dot"></i>Useful technology and digital guides, made clearer</span><span>English + हिन्दी</span></div></div>
<header class="header"><div class="wrap header-inner"><a class="brand" href="/" aria-label="{esc(SITE)} home"><span class="brand-mark">FB</span><span class="brand-name">{esc(SITE)}<small>Practical guides in Hindi + English</small></span></a><button class="mobile-menu" data-menu-button aria-expanded="false" aria-label="Toggle navigation">☰</button><nav class="nav" data-site-nav>{nav_html(active)}</nav></div></header>'''

def footer():
    email_text = EMAIL if EMAIL and 'REPLACE_WITH' not in EMAIL else 'Update contact_email in site_config.json before launch'
    return f'''<footer class="footer"><div class="wrap"><div class="footer-grid"><div><a class="brand" href="/"><span class="brand-mark">FB</span><span class="brand-name">{esc(SITE)}<small>Practical guides in Hindi + English</small></span></a><p>{esc(CONFIG.get('description',''))} We aim to publish clear, useful and carefully checked guides.</p></div><div><h4>Explore</h4><div class="footer-links"><a href="/categories/">All topics</a>{''.join(f'<a href="/categories/{c["slug"]}/">{esc(c["name"])}</a>' for c in CATEGORIES)}</div></div><div><h4>About & policies</h4><div class="footer-links"><a href="/about/">About us</a><a href="/contact/">Contact</a><a href="/privacy-policy/">Privacy policy</a><a href="/disclaimer/">Disclaimer</a><a href="/editorial-policy/">Editorial policy</a></div></div></div><div class="footer-bottom"><span>© {date.today().year} {esc(SITE)}. Content is for informational purposes.</span><span>Contact: {esc(email_text)}</span></div></div></footer><script src="/assets/script.js" defer></script>'''

def card(post):
    cat=CAT_MAP[post['category']]
    img=post.get('image_url','')
    image_html=f'<img src="{esc(img)}" alt="{esc(post.get("image_alt") or post["title"])}" loading="lazy" decoding="async">' if img else f'<div class="image-fallback" aria-hidden="true">{cat["icon"]}</div>'
    terms=' '.join([post.get('title',''),post.get('excerpt',''),post.get('category',''),post.get('language',''),*post.get('tags',[])])
    return f'''<article class="post-card" data-post-card data-category="{esc(cat['slug'])}" data-language="{esc(post.get('language','en'))}" data-search="{esc(terms)}"><a class="post-image" href="/articles/{esc(post['slug'])}/">{image_html}</a><div class="post-body"><div class="post-meta"><a class="tag" href="/categories/{esc(cat['slug'])}/">{esc(cat['name'])}</a><span>{esc(date_human(post.get('date','')))}</span><span>{esc(post.get('read_minutes',5))} min read</span></div><h3><a href="/articles/{esc(post['slug'])}/">{esc(post['title'])}</a></h3><p>{esc(post.get('excerpt',''))}</p><a class="read-link" href="/articles/{esc(post['slug'])}/">Read the guide →</a></div></article>'''

def post_body(post):
    out=[]
    intro=post.get('intro','')
    if intro: out.append(f'<p>{esc(intro)}</p>')
    for section in post.get('sections',[]):
        out.append(f'<h2>{esc(section.get("heading",""))}</h2>')
        for para in section.get('paragraphs',[]): out.append(f'<p>{esc(para)}</p>')
        bullets=section.get('bullets',[])
        if bullets: out.append('<ul>'+''.join(f'<li>{esc(x)}</li>' for x in bullets)+'</ul>')
    return '\n'.join(out)

def render_article(post):
    slug=post['slug']; path=f'articles/{slug}/'; cat=CAT_MAP[post['category']]; lang=post.get('language','en')
    title=post['title']; desc=post.get('seo_description') or post.get('excerpt','')
    img=post.get('image_url','')
    image_markup=f'<figure class="article-hero"><img src="{esc(img)}" alt="{esc(post.get("image_alt") or title)}">'+(f'<figcaption class="image-credit">{esc(post.get("image_credit",""))}'+(f' · <a href="{esc(post.get("image_source_url"))}" rel="nofollow noopener" target="_blank">Image source</a>' if post.get('image_source_url') else '')+(f' · <a href="{esc(post.get("image_license_url"))}" rel="nofollow noopener" target="_blank">{esc(post.get("image_license"))} licence</a>' if post.get('image_license_url') else '')+'</figcaption>' if post.get('image_credit') else '')+'</figure>' if img else ''
    tags=''.join(f'<span class="tag">{esc(t)}</span>' for t in post.get('tags',[]))
    sources=post.get('sources',[])
    source_html=''
    if sources:
        source_html='<h2>Sources and further reading</h2><ul>'+''.join(f'<li><a href="{esc(s.get("url",""))}" target="_blank" rel="noopener noreferrer">{esc(s.get("title") or s.get("url"))}</a></li>' for s in sources if s.get('url','').startswith('https://'))+'</ul>'
    faqs=post.get('faqs',[])
    faq_html=''
    if faqs:
        faq_html='<h2>Frequently asked questions</h2>'+''.join(f'<div class="faq-item"><h3>{esc(f.get("question",""))}</h3><p>{esc(f.get("answer",""))}</p></div>' for f in faqs)
    canonical=site_url(path)
    breadcrumb=f'<div class="crumbs"><a href="/">Home</a> / <a href="/categories/{esc(cat["slug"])}/">{esc(cat["name"])}</a> / {esc(title)}</div>'
    # AdSense Auto Ads is injected via the head when explicitly enabled and a valid publisher ID exists.
    # Do not display empty placeholder blocks to readers.
    ads=''
    content=f'''{head(title+' | '+SITE,desc,path,lang,img,post)}<body>{header(cat['name'])}<main class="wrap"><div class="article-wrap"><article class="article">{breadcrumb}<div class="post-meta"><a class="tag" href="/categories/{esc(cat['slug'])}/">{esc(cat['name'])}</a><span>{esc(date_human(post.get('date',''),lang))}</span><span>{esc(post.get('read_minutes',5))} min read</span><span>By {esc(post.get('author',SITE))}</span></div><h1>{esc(title)}</h1><p class="article-deck">{esc(post.get('excerpt',''))}</p>{image_markup}{ads}<div class="article-content">{post_body(post)}{faq_html}{source_html}</div><div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:25px">{tags}</div><div class="notice" style="margin-top:25px">Editorial note: We aim to provide helpful information and update articles when important details change. Verify time-sensitive information against official sources.</div></article><aside class="article-sidebar"><div class="side-box"><h3>About this guide</h3><p>{esc(cat['description'])}</p></div><div class="side-box"><h3>Explore more</h3><div class="side-links">{''.join(f'<a href="/categories/{c["slug"]}/">{esc(c["name"])} →</a>' for c in CATEGORIES)}</div></div><div class="side-box"><h3>Read responsibly</h3><p>Check linked sources for important or changing information. If you spot an error, please <a href="/contact/">contact us</a>.</p></div></aside></div></main>{footer()}</body></html>'''
    return content

def page_shell(title,description,body,path='',active=''):
    return f'{head(title,description,path)}<body>{header(active)}{body}{footer()}</body></html>'

def render_home(posts):
    en_count=sum(1 for p in posts if p.get('language')=='en'); hi_count=sum(1 for p in posts if p.get('language')=='hi')
    featured=posts[0] if posts else None
    feature_html=''
    if featured:
        img=featured.get('image_url','')
        cat=CAT_MAP[featured['category']]
        fimg=f'<img src="{esc(img)}" alt="{esc(featured.get("image_alt") or featured["title"])}" loading="eager">' if img else '<div class="image-fallback">✳</div>'
        feature_html=f'''<a class="featured-image" href="/articles/{esc(featured['slug'])}/">{fimg}</a><div class="featured-copy"><div class="post-meta"><span class="tag">Featured guide</span><span>{esc(cat['name'])}</span><span>{esc(featured.get('read_minutes',5))} min read</span></div><h3><a href="/articles/{esc(featured['slug'])}/">{esc(featured['title'])}</a></h3><p>{esc(featured.get('excerpt',''))}</p><a class="btn" style="background:var(--brand);color:white" href="/articles/{esc(featured['slug'])}/">Read featured guide →</a></div>'''
    no_posts='<div class="empty-state">No published posts yet. Review and publish your first article JSON, then run the site builder.</div>'
    cat_cards=''.join(f'<a class="category-card" href="/categories/{c["slug"]}/"><span class="cat-icon">{c["icon"]}</span><h3>{esc(c["name"])}</h3><p>{esc(c["short"])}</p></a>' for c in CATEGORIES)
    cards=''.join(card(p) for p in posts)
    body=f'''<main><section class="hero"><div class="wrap"><div class="hero-panel"><div class="eyebrow"><span class="pill">Independent publication</span><span>ENGLISH · हिंदी</span></div><h1>Useful answers.<br><span>Smarter digital life.</span></h1><p>{esc(CONFIG.get('description',''))} Straightforward tutorials, practical explainers and ideas you can put to work.</p><div class="hero-actions"><a class="btn btn-primary" href="#latest">Explore latest articles ↘</a><a class="btn btn-ghost" href="/categories/">Browse all topics</a></div></div></div></section>
<section class="section"><div class="wrap"><div class="section-head"><div><div class="kicker">Browse by interest</div><h2>Find your next answer</h2><p class="section-sub">Focused sections make useful guides easy to discover.</p></div><a class="text-link" href="/categories/">All categories →</a></div><div class="category-grid">{cat_cards}</div></div></section>
<section class="section"><div class="wrap"><div class="section-head"><div><div class="kicker">Editor's pick</div><h2>Start with something useful</h2></div></div><div class="featured">{feature_html or no_posts}</div></div></section>
<section class="section" id="latest"><div class="wrap"><div class="section-head"><div><div class="kicker">Freshly published</div><h2>Latest articles</h2><p class="section-sub">Guides written to answer specific questions clearly.</p></div><span class="text-link" data-result-count>{len(posts)} articles</span></div><div class="toolbar"><label class="search-box"><span class="search-icon">⌕</span><input type="search" data-post-search placeholder="Search guides, tools or questions…" aria-label="Search articles"></label><select class="filter-select" data-category-filter aria-label="Filter by category"><option value="all">All categories</option>{''.join(f'<option value="{c["slug"]}">{esc(c["name"])}</option>' for c in CATEGORIES)}</select><select class="filter-select" data-language-filter aria-label="Filter by language"><option value="all">All languages</option><option value="en">English</option><option value="hi">हिन्दी</option></select></div><div class="post-grid">{cards}</div><div class="empty-state" data-empty-state hidden>No article matches your search. Try a different keyword or filter.</div></div></section>
<section class="section"><div class="wrap"><div class="newsletter"><div><h2>Useful knowledge, without the noise.</h2><p>Explore practical guides, check sources and come back as the library grows.</p></div><a class="btn" href="/editorial-policy/">How we create content →</a></div></div></section></main>'''
    return page_shell(SITE+' — AI, Technology, Apps & Career Guides',CONFIG.get('description',''),body,'')

def render_category(cat, posts):
    matching=[p for p in posts if p.get('category')==cat['name']]
    cards=''.join(card(p) for p in matching) or '<div class="empty-state">New guides for this topic are being prepared. Please check back soon.</div>'
    body=f'''<main class="wrap"><section class="page-intro"><div class="crumbs"><a href="/">Home</a> / Categories / {esc(cat['name'])}</div><div class="kicker">Explore topic</div><h1>{esc(cat['name'])}</h1><p>{esc(cat['description'])}</p><p class="section-sub">{len(matching)} published article(s) in this topic.</p></section><section class="section"><div class="post-grid">{cards}</div></section><div style="padding:22px 0 60px"><a class="text-link" href="/categories/">← Browse all categories</a></div></main>'''
    return page_shell(cat['name']+' | '+SITE,cat['description'],body,f'categories/{cat["slug"]}/',cat['name'])

def render_categories_index(posts):
    cards=''.join(f'<a class="category-card" href="/categories/{c["slug"]}/"><span class="cat-icon">{c["icon"]}</span><h3>{esc(c["name"])}</h3><p>{esc(c["description"])}</p><p style="margin-top:10px;font-weight:800;color:var(--brand)">{sum(1 for p in posts if p.get("category")==c["name"])} articles →</p></a>' for c in CATEGORIES)
    body=f'''<main class="wrap"><section class="page-intro"><div class="crumbs"><a href="/">Home</a> / Categories</div><div class="kicker">Topic library</div><h1>Explore all categories</h1><p>Choose a topic to find focused, practical guides. We publish in English and Hindi as suitable for the reader and subject.</p></section><section class="section"><div class="category-grid">{cards}</div></section></main>'''
    return page_shell('All Categories | '+SITE,'Browse all FactBlogger topics and guides.',body,'categories/')

def legal_pages():
    email = EMAIL if EMAIL and 'REPLACE_WITH' not in EMAIL else '[Add a real contact email in site_config.json before publishing]'
    common='FactBlogger is an independent informational website. We aim to keep our content useful, clear and appropriately sourced.'
    pages={
      'about':('About Us','Learn what FactBlogger covers and how we approach useful, reader-first content.',f'''<h1>About {esc(SITE)}</h1><p>{esc(CONFIG.get('description',''))}</p><h2>What we cover</h2><ul>{''.join(f'<li><strong>{esc(c["name"])}</strong> — {esc(c["description"])}</li>' for c in CATEGORIES)}</ul><h2>Our approach</h2><p>{esc(common)} We may use AI-assisted tools for outlining, drafting, translation and editing, but generated claims are not automatically treated as facts. Articles should be reviewed for accuracy, usefulness and sourcing.</p><h2>Corrections</h2><p>If you spot an error or a broken link, please contact us with the article URL and a source that supports your correction.</p>'''),
      'contact':('Contact Us','Contact FactBlogger with questions, feedback or correction requests.',f'''<h1>Contact Us</h1><p>Have a question, suggestion, collaboration idea or correction? We welcome helpful feedback.</p><p>Email: <a href="mailto:{esc(email)}">{esc(email)}</a></p><p>For factual corrections, please include the article URL and the reliable source supporting the correction. For privacy-related requests, use the subject “Privacy request”.</p><p>We aim to review messages and respond when possible.</p>'''),
      'privacy-policy':('Privacy Policy','How FactBlogger may process information and how third-party services are handled.',f'''<h1>Privacy Policy</h1><p><strong>Last updated:</strong> {date.today().strftime('%d %B %Y')}</p><p>This policy describes general practices for this website. It must be reviewed and updated to reflect the services that are actually enabled before launch.</p><h2>Information you provide</h2><p>If you email us, we receive the information you choose to send, such as your email address and message. We use it to respond and manage feedback.</p><h2>Hosting and technical information</h2><p>When hosted by Cloudflare Pages or another provider, the provider may process technical request information, including IP address and logs, for security and service operation under its own terms and privacy policy.</p><h2>Analytics and cookies</h2><p>If analytics, embedded content or other third-party tools are enabled, they may use cookies or similar technologies. This policy must be updated to name the tools in use and explain applicable choices and consent requirements.</p><h2>Advertising</h2><p>If Google AdSense or another advertising service is enabled, advertising vendors may use cookies or similar technologies in accordance with applicable policies, settings and consent requirements. We will update this disclosure before enabling advertising.</p><h2>External links</h2><p>Articles may link to external websites. Their privacy practices are controlled by their respective operators.</p><h2>Children</h2><p>This website is not specifically designed to collect personal information from children.</p><h2>Contact</h2><p>For privacy questions, contact {esc(email)}.</p>'''),
      'disclaimer':('Disclaimer','Important limitations concerning information on FactBlogger.',f'''<h1>Disclaimer</h1><p>Content on {esc(SITE)} is provided for general informational and educational purposes. We aim for accuracy but cannot guarantee that every page is complete, current or error-free.</p><h2>AI-assisted content</h2><p>Some content may be prepared with AI-assisted tools. Output can contain mistakes, so important claims should be verified against appropriate primary or official sources.</p><h2>Technology and code</h2><p>Software instructions and code examples are provided for learning. Review them before use and back up important data before significant changes.</p><h2>Financial, medical and legal topics</h2><p>Where present, such articles are general information and are not a substitute for advice from a qualified professional.</p><h2>External links and commercial relationships</h2><p>We do not control external sites. If affiliate relationships or paid promotions are introduced, relevant disclosures will be provided where required.</p><h2>Contact</h2><p>{esc(email)}</p>'''),
      'editorial-policy':('Editorial Policy','How FactBlogger selects, researches, reviews and updates content.',f'''<h1>Editorial Policy</h1><h2>Topic selection</h2><p>We prioritize clear reader questions, practical usefulness and topics that can be explained accurately.</p><h2>Research and sourcing</h2><p>We aim to prioritize primary sources, official documentation and authoritative references for claims that require verification. Time-sensitive details should be checked against current sources before publication.</p><h2>AI-assisted writing</h2><p>AI tools may support topic research, outlining, drafting, translation and editing. AI output is not automatically considered accurate or publishable.</p><h2>Review process</h2><p>Articles should be reviewed for correctness, clarity, originality, links, language quality and potential duplication. High-impact or rapidly changing subjects require extra care.</p><h2>Images and copyright</h2><p>We aim to use original or appropriately licensed images and provide attribution where the applicable licence requires it. Image licences should be checked individually before publication.</p><h2>Corrections and updates</h2><p>We review correction requests and update content when a meaningful correction is warranted. Substantial changes may be reflected in the update date.</p><h2>Contact</h2><p>{esc(email)}</p>''')
    }
    out={}
    for slug,(title,desc,body) in pages.items():
        page=f'<main class="wrap"><section class="page-intro"><div class="crumbs"><a href="/">Home</a> / {esc(title)}</div></section><article class="policy-content">{body}</article></main>'
        out[slug]=page_shell(title+' | '+SITE,desc,page,slug+'/')
    return out

def _remove_readonly(func, path, exc_info):
    """Retry deletion after clearing Windows read-only attributes.

    This helps with files copied from ZIP archives or synchronized folders.
    It cannot remove a file that is actively locked by another process.
    """
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        # Let the caller show a clear recovery message if the path is still locked.
        raise


def clean_public_directory():
    if not PUBLIC.exists():
        return
    last_error = None
    for attempt in range(3):
        try:
            shutil.rmtree(PUBLIC, onerror=_remove_readonly)
            return
        except OSError as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1.0)
    print('ERROR: Could not clear the generated public/ folder.')
    print('Close the local preview server and any program using files inside public/.')
    print('This project is currently under OneDrive/Desktop; OneDrive sync can lock files.')
    print(r'If it persists, copy/extract the project to C:\FactBlogger\factblogger-site and run the build there.')
    print('You can also run: attrib -R "public\\*" /S /D')
    print(f'Original error: {last_error}')
    raise SystemExit(1)


def main():
    clean_public_directory()
    PUBLIC.mkdir(parents=True)
    shutil.copytree(ASSETS, PUBLIC/'assets')
    # Preserve Search Console HTML file verification across every rebuild.
    for verify_file in ROOT.glob('google*.html'):
        if verify_file.is_file():
            shutil.copy2(verify_file, PUBLIC / verify_file.name)
    posts=load_posts()
    # Root homepage and article URLs
    (PUBLIC/'index.html').write_text(render_home(posts),encoding='utf-8')
    for post in posts:
        p=PUBLIC/'articles'/post['slug']/'index.html';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(render_article(post),encoding='utf-8')
    for cat in CATEGORIES:
        p=PUBLIC/'categories'/cat['slug']/'index.html';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(render_category(cat,posts),encoding='utf-8')
    p=PUBLIC/'categories'/'index.html';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(render_categories_index(posts),encoding='utf-8')
    for slug,body in legal_pages().items():
        p=PUBLIC/slug/'index.html';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(body,encoding='utf-8')
    not_found_body = '<main class="wrap"><section class="page-intro"><h1>Page not found</h1><p>This page may have moved or the address may be incorrect.</p><p><a class="btn btn-primary" href="/">Return to FactBlogger home</a> <a class="btn" href="/categories/">Browse topics</a></p></section></main>'
    (PUBLIC/'404.html').write_text(page_shell('Page Not Found | '+SITE,'The requested page could not be found.',not_found_body,'404.html'),encoding='utf-8')
    # RSS feed
    rss_items=[]
    for post in posts[:30]:
        link=site_url(f'articles/{post["slug"]}/')
        rss_items.append(f'<item><title>{esc(post["title"])}</title><link>{esc(link)}</link><guid>{esc(link)}</guid><pubDate>{datetime.fromisoformat(date_iso(post.get("date")) ).strftime("%a, %d %b %Y 00:00:00 +0000")}</pubDate><description>{esc(post.get("excerpt",""))}</description></item>')
    rss=f'''<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{esc(SITE)}</title><link>{esc(BASE or "/")}</link><description>{esc(CONFIG.get("description",""))}</description>{''.join(rss_items)}</channel></rss>'''
    (PUBLIC/'rss.xml').write_text(rss,encoding='utf-8')
    # Sitemap with all static indexable pages
    paths=['','categories/']+[f'categories/{c["slug"]}/' for c in CATEGORIES]+[f'{s}/' for s in legal_pages().keys()]+[f'articles/{p["slug"]}/' for p in posts]
    if BASE_OK:
        urls=[]
        for path in paths:
            urls.append(f'<url><loc>{esc(site_url(path))}</loc><changefreq>{"weekly" if path=="" or path=="categories/" else "monthly"}</changefreq><priority>{"1.0" if path=="" else "0.7" if path.startswith("articles/") else "0.6"}</priority></url>')
        sitemap='<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join(urls)+'</urlset>'
    else:
        sitemap='<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset><!-- Set site_config.json base_url before deployment. -->'
    (PUBLIC/'sitemap.xml').write_text(sitemap,encoding='utf-8')
    (PUBLIC/'robots.txt').write_text(('User-agent: *\nAllow: /\nSitemap: '+site_url('sitemap.xml')+'\n') if BASE_OK else 'User-agent: *\nDisallow: /\n',encoding='utf-8')
    (PUBLIC/'.nojekyll').write_text('',encoding='utf-8')
    (PUBLIC/'_headers').write_text('''/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  X-Frame-Options: SAMEORIGIN
/assets/*
  Cache-Control: public, max-age=86400
''',encoding='utf-8')
    pub=CONFIG.get('adsense_publisher_id','').strip()
    if re.fullmatch(r'ca-pub-\d{16}',pub):
        (PUBLIC/'ads.txt').write_text(f'google.com, {pub[7:]}, DIRECT, f08c47fec0942fa0\n',encoding='utf-8')
    print(f'Built {len(posts)} published article(s), {len(CATEGORIES)} categories and {len(legal_pages())} policy/about pages into: {PUBLIC}')
    if not BASE_OK:
        print('ACTION NEEDED: set site_config.json base_url to your real Cloudflare Pages URL before launch; the temporary build is noindexed until configured.')
    if not EMAIL or 'REPLACE_WITH' in EMAIL:
        print('ACTION NEEDED: replace contact_email in site_config.json before publishing.')
    if BASE_OK and not re.fullmatch(r'https://[A-Za-z0-9.-]+(?::[0-9]+)?/', BASE):
        print('WARNING: base_url should be the HTTPS origin plus trailing slash, without a path.')
    if not pub:
        print('AdSense is not configured yet (correct for a new site). No ad script or ads.txt was added.')

if __name__=='__main__': main()
