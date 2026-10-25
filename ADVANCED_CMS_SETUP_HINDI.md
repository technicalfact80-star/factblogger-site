# FactBlogger Advanced CMS — Setup Guide (Hindi)

## Ye upgrade kya add karta hai?

- Local admin panel: category add/edit/delete, manual article editor, draft list, article editing, and publishing.
- Dynamic `categories.json`: new category site navigation, category page, generator choices and sitemap mein use hoti hai.
- AI draft generation through local Ollama; no per-request paid AI API required.
- RSS/Atom news source manager, latest headline dashboard, AI news-draft creation.
- Daily automation runner: evergreen topic queue + configurable news feeds.
- Guarded news auto-publish option. Default OFF; it requires two distinct source domains, useful length/sections/FAQs and reusable image metadata. Automated checks cannot prove truth, originality or legal rights.
- Windows Task Scheduler batch file.
- Local-only admin at `http://127.0.0.1:8787` (not exposed on public site).

## IMPORTANT: Preserve your existing website settings

Do not replace your existing `site_config.json`, `content/posts/`, `.git/` or GitHub repository. This ZIP is an overlay/upgrade package. Extract/copy only the included files into the root folder that already contains `build_site.py` and `site_config.json`; allow replacing `build_site.py` and `generate_post.py`. Keep your existing live `base_url`, contact email and Search Console verification settings.

Back up the folder first, for example copy it to `C:\FactBlogger-backup`.

## Install the upgrade

1. Stop preview/admin windows using `Ctrl+C`.
2. Extract this upgrade ZIP into your current project root, e.g. `C:\Users\user\OneDrive\Desktop\FactBlogger\factblogger-site`.
3. Make sure these files exist in the root: `admin_server.py`, `categories.json`, `news_sources.json`, `automation_config.json`, `automation_runner.py`, `start_admin.bat`, `run_daily_automation.bat`, `build_site.py`, `generate_post.py`.
4. Keep `site_config.json` from your current live project. Do not replace it with an example file.
5. Check current config remains correct:

```powershell
Get-Content .\site_config.json
```

`base_url` should be your exact live origin with a trailing slash (`https://fact.technicalfact80.workers.dev/` if that is still your active site), and `contact_email` should be your real contact email. Do not publish placeholder values.
6. Compile-check and rebuild:

```powershell
py -m py_compile admin_server.py automation_runner.py build_site.py generate_post.py
py build_site.py
py check_site.py
```

7. Confirm the root Google verification file is present. This build system copies root-level `google*.html` verification files into `public/` on each rebuild.
8. Test local preview using `start_preview.bat`.

## Start the admin CMS

1. Double-click `start_admin.bat`.
2. Open `http://127.0.0.1:8787` in Chrome.
3. Keep the black terminal window open while you use the admin.
4. This admin is intentionally bound only to localhost. Do not port-forward it or deploy it publicly.

### Categories

- Open **Categories**.
- Fill name, unique URL slug (`lowercase-words-with-hyphens`), icon, short description and full description.
- Save. The category updates `categories.json` and triggers a local build.
- Tick **Also push category changes to live website** if your git repository/Cloudflare deployment is healthy and you want changes online immediately. Otherwise use Dashboard → Rebuild website and tick the push option later.
- Deletion is blocked if any article/draft uses that category. Moving an existing category to a new slug changes its URL; plan redirects carefully before doing so on an established site.

### Manual article

- Open **New article**.
- Enter title, unique slug, category, language, excerpt, SEO description, intro and article body.
- Use `## Section heading`, blank lines for paragraphs and `- item` for bullets.
- Add FAQs using one per line: `Question :: Answer`.
- Fill image URL, alt text, image source URL, licence name/credit, licence URL, and source URLs.
- Save draft to keep it unpublished. For publishing, the local form requires at least three sections and image/licence fields. These are basic gates, not a quality guarantee.
- To deploy after publishing, tick **Also push to GitHub / live deploy** before clicking Publish locally. Git credentials and the repository remote must already work.

### AI article drafts

Install Ollama from https://ollama.com/download/windows. Then in PowerShell:

```powershell
ollama pull qwen2.5:3b
ollama list
```

Ollama needs disk space/RAM and the computer must be on for scheduled generation. In admin, use **New article → Generate an AI draft**, choose a topic/category/language, and add trusted HTTPS source URLs. Draft will open in the editor. Verify all claims and image rights before publishing.

### News feed monitor

- Open **News sources**. Initial sources include official PIB releases, Google India Blog, OpenAI News and GitHub Blog RSS feeds.
- You can edit the source list JSON; each entry needs name, HTTPS RSS/Atom URL, domain, existing category, language (`en`/`hi`), enabled boolean and trust label.
- Open **Latest news → Refresh feeds** to pull current headlines.
- Use **Create AI draft from this headline** to create a news explainer. It uses the original article link as research input; do not republish source article text wholesale.

## Daily automation

`automation_config.json` is editable in the Admin → Automation settings page.

Defaults:
- Evergreen topic queue daily: ON (one draft per run while queue has items)
- News feed fetch: ON (up to two news drafts per run)
- News auto-publish: OFF
- Evergreen auto-publish: OFF

Run once manually from Admin → Run daily automation now, or in PowerShell:

```powershell
py automation_runner.py
```

To schedule (automatic option): open PowerShell in the project root and run `powershell -ExecutionPolicy Bypass -File .\install_daily_task.ps1`. It creates a task for daily 9:00 AM. You can also use the GUI method below.

GUI method:
1. Open Windows Task Scheduler → Create Basic Task.
2. Name it `FactBlogger Daily Automation`.
3. Trigger `Daily`; choose a time (e.g. 9:00 AM).
4. Action `Start a program`.
5. Program: `C:\Windows\System32\cmd.exe`
6. Arguments: `/c "C:\path\to\factblogger-site\run_daily_automation.bat"`
7. Start in: the project root folder.
8. Test using right-click → Run. Read `logs\automation.log`.

The PC needs to be awake and connected to the internet; Ollama must run. This is not cloud-hosted compute and will not run if your PC is off.

### Add more evergreen topics

Open **Topic queue** from Admin, add a unique reader question, category, language and official/trustworthy source URLs. The daily runner consumes one next queue entry and creates a draft by default. Do not delete earlier queue items casually; `draft_state.json` stores a numeric queue index.

## Unattended auto-publishing — use only after testing

You can enable `auto_publish_evergreen` or `auto_publish_news` in Admin → Automation settings. The system will still block some low-quality cases. News autopublishing requires at least two apparently independent source domains with overlapping headline terms, article length/sections/FAQs, source references and a clearly reusable image licence. Headline similarity is not proof that sources independently corroborate each claim. No automated gate can fully fact-check content.

Recommended workflow for an AdSense-focused site: let automation create drafts for 1–2 weeks, inspect output and image licences, then only consider gated autopublishing for low-risk evergreen guides. Keep breaking news, finance, health, politics and legal topics in draft/review mode. There is no setting or article count that guarantees AdSense approval or Google ranking.

## Deployment after changes

- If you ticked a push checkbox, admin will build the static site, commit only the selected files/categories and `public/`, then `git push`.
- Cloudflare deployment must be connected to the same repository/branch. Wait for deployment success.
- Check homepage, new category URL, article URL, `/sitemap.xml`, `/robots.txt`, `/rss.xml` and the Search Console verification file.
- In Search Console, submit `sitemap.xml` if not already submitted and inspect new URLs. Google decides whether and when to index/rank each page.

## Key limitation

This package adds a local CMS, not a public multi-user server backend. Admin changes run on the owner's PC and go live by committing/pushing static JSON + generated HTML. If you later want a public dashboard accessible from any device with user accounts, roles and a database, that is a different full-stack system (for example Cloudflare Worker + D1 + authentication). Do not expose this local admin to the Internet.
