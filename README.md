# FactBlogger — independent AI-assisted blogging website

FactBlogger is a responsive, static HTML/CSS/JavaScript publication. It does not use Blogger or WordPress. The site builder and local AI draft generator use Python's standard library; AI draft generation requires Ollama on your own computer.

## What is included

- Responsive homepage, category pages, searchable article cards and readable article URLs
- Five categories: AI & Technology, Education & Careers, Blogging & SEO, Apps & Software, India Digital Guides
- Hindi and English article support
- About, Contact, Privacy Policy, Disclaimer and Editorial Policy pages
- Custom 404 page, canonical URLs, robots.txt, XML sitemap, RSS feed, Open Graph metadata and Article/WebSite structured data
- Google Search Console HTML meta-token support (`google_site_verification` in `site_config.json`)
- Optional AdSense loader and `ads.txt` generation when a valid publisher ID is configured
- Local AI article drafts using Ollama, plus image discovery via Wikimedia Commons when a clearly reusable licence is available
- Draft-first workflow with manual review before publication; daily draft scheduling can be configured locally
- Local technical preflight tool (`check_site.py`) to find broken internal links and launch blockers

## Before going live

Edit `site_config.json`:

1. `base_url`: replace `https://YOUR-PROJECT.pages.dev/` with the exact HTTPS origin given to your live Cloudflare Pages project, including the trailing slash. Example: `https://factblogger-abc.pages.dev/`. Do not include a path.
2. `contact_email`: use an address that you actually control.
3. `google_site_verification`: add the token from Search Console only if you choose HTML meta-tag verification. Leave blank otherwise.
4. Keep `adsense_publisher_id` blank and `adsense_auto_ads_enabled` false until you have your own publisher ID and are ready to add AdSense code for verification/review.

If `base_url` is unset or still a placeholder, the build intentionally emits `noindex,nofollow`, `robots.txt` blocks crawlers, and the sitemap has no URLs. This prevents accidentally publishing the default placeholder URLs. Set the real URL and rebuild before requesting indexing.

## Local preview on Windows

1. Install Python 3.11 or newer from https://www.python.org/downloads/ and enable **Add Python to PATH**.
2. Extract the ZIP into a normal folder such as `C:\Users\YOURNAME\Documents\factblogger-site`.
3. Double-click `start_preview.bat`.
4. Visit http://localhost:8000. Keep the terminal window open while previewing.

To run an integrity check from PowerShell in the project folder:

```powershell
py build_site.py
py check_site.py
```

The local preflight will intentionally warn/block launch readiness until you provide the real live URL and contact email. It cannot forecast Google ranking or AdSense approval.

## Free hosting with GitHub + Cloudflare Pages

This can be developed and initially hosted without a paid custom domain or paid AI API. A custom domain, if desired or needed by your monetization setup, is separate and may cost money. Cloudflare or Google plan/policy details can change; verify the current official documentation before deploying.

1. Create a GitHub repository called `factblogger-site`.
2. Open PowerShell in this folder and initialize/push the code (replace the username):

```powershell
git init
git branch -M main
git add .
git commit -m "Create FactBlogger website"
git remote add origin https://github.com/YOUR-GITHUB-USERNAME/factblogger-site.git
git push -u origin main
```

3. In Cloudflare, go to **Workers & Pages → Create application → Pages → Connect to Git** and connect the repository. Use branch `main`, framework preset **None**, build command `exit 0`, and output directory `public`.
4. Deploy. Copy the exact `https://...pages.dev/` origin Cloudflare assigns.
5. Edit `site_config.json`: set the real `base_url` and your contact email. Rebuild and push:

```powershell
py build_site.py
py check_site.py
git add site_config.json public
git commit -m "Configure FactBlogger live site"
git push
```

6. Open the live URL in an incognito window and check homepage, all article links, category pages, policy pages, mobile layout, `https://YOUR-SITE/sitemap.xml`, `https://YOUR-SITE/robots.txt`, and `https://YOUR-SITE/404.html`.

## Add or edit an article

Each published post is a JSON file under `content/posts/`. Copy an existing file and update its unique `slug`, title, excerpt, language (`en` or `hi`), exact category name, date, image information, intro, section paragraphs, FAQs, tags and supporting sources. Set `published` to `true` only after editorial review.

Then run:

```powershell
py build_site.py
py check_site.py
```

Preview locally before committing and pushing changes.

## Local AI draft generation (no paid model API)

1. Install Ollama from https://ollama.com/download/windows.
2. In PowerShell run `ollama pull qwen2.5:3b`. Model size and performance depend on your machine and disk/RAM.
3. Generate a draft with verified source URLs, for example:

```powershell
py generate_post.py --topic "How to use AI tools responsibly for college projects" --category "AI & Technology" --language en --source-url "https://developers.google.com/search/docs/fundamentals/using-gen-ai-content"
```

4. Draft files are placed in `drafts/` and are **not public**. Check each factual claim, linked source, image suitability/licence, originality, language quality and search intent.
5. After all checks are complete, run `py publish_post.py YOUR-DRAFT-FILENAME.json`. Use `--push` only when the repository is connected and ready to deploy.
6. `daily_draft_scheduled.bat` is designed for Windows Task Scheduler: it creates one next-in-queue local draft and appends output to `logs/daily-draft.log`. Your PC must be powered on and Ollama must be available. This does not publish drafts. For unattended publishing, `daily_autopublish_EXPERIMENTAL.bat` exists, but it must not be scheduled until you have manually reviewed many outputs and accept the risk. It still enforces structural/source/image gates, but no automatic gate can guarantee that an article is factual, original or AdSense-ready.

Unreviewed auto-publishing is deliberately not the default. Automated length/source/image checks cannot prove factual accuracy or originality. Avoid publishing generic pages at scale purely for search traffic; see Google Search's scaled-content-abuse policy.

## AdSense: safety and approval notes

- Approval is controlled by Google and cannot be guaranteed by code, article count, SEO tags, or any developer.
- Google says the site should provide original, useful content, clear navigation and a good user experience. There is no published universal minimum post count or word count that guarantees approval.
- Keep the privacy disclosure accurate for the services actually used; add the relevant ad/cookie disclosure before enabling ads.
- Add your site in AdSense, verify ownership using the method Google provides, install the provided code or token exactly as directed, and wait for the site review. Ads should run only after AdSense marks the site ready.
- `ads.txt` is written only when `adsense_publisher_id` is a valid `ca-pub-` ID. Do not invent an ID. `adsense_auto_ads_enabled` controls whether the AdSense loader appears across pages.
- Never click your own ads, ask anyone to click ads, or buy invalid traffic.
- A free hosting subdomain is not guaranteed to be accepted in every account/site flow. If AdSense cannot accept or verify the assigned subdomain, you may need a domain you control; domain registration may not be free.

Official references:

- AdSense site-readiness guide: https://support.google.com/adsense/answer/7299563
- AdSense eligibility: https://support.google.com/adsense/answer/9724
- AdSense site management: https://support.google.com/adsense/answer/12131223
- Google Search generative-AI content guidance: https://developers.google.com/search/docs/fundamentals/using-gen-ai-content
- Google Search spam policies: https://developers.google.com/search/docs/essentials/spam-policies
- Search Console sitemap guidance: https://developers.google.com/search/docs/crawling-indexing/sitemaps/overview
