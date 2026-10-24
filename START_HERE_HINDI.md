# FactBlogger — Hindi setup guide

Ye Blogger/WordPress website nahi hai. Ye independent static website hai. Public website `public/` folder se build hoti hai; local AI draft generator tumhare PC par Ollama use karta hai.

## 1. Pehle apne computer par website chalao

1. `FactBlogger-website.zip` extract karo.
2. Python 3.11+ install karo: https://www.python.org/downloads/ . Installation mein **Add Python to PATH** select karo.
3. Extracted folder mein `start_preview.bat` par double-click karo.
4. Browser mein `http://localhost:8000` kholo. Preview ke waqt black terminal window band mat karna.
5. Homepage, article cards, category pages, footer links aur mobile layout check karo.

PowerShell se test karna ho:

```powershell
py build_site.py
py check_site.py
```

## 2. Live website free hosting par publish karo

### GitHub

1. https://github.com/ par login karo aur `factblogger-site` repository create karo.
2. Project folder mein PowerShell kholo, phir commands chalao. `YOUR-GITHUB-USERNAME` ko apne username se replace karna:

```powershell
git init
git branch -M main
git add .
git commit -m "Create FactBlogger website"
git remote add origin https://github.com/YOUR-GITHUB-USERNAME/factblogger-site.git
git push -u origin main
```

Agar `git` command nahi milti, Git for Windows install karo: https://git-scm.com/download/win .

### Cloudflare Pages

1. https://dash.cloudflare.com/ kholo.
2. **Workers & Pages → Create application → Pages → Connect to Git** choose karo.
3. GitHub ka `factblogger-site` repository connect karo.
4. Branch `main`, Framework preset `None`, Build command `exit 0`, Output directory `public` rakho.
5. Deploy ke baad Cloudflare jo `https://...pages.dev/` address de, usko copy karo.

### Live URL configure karo — ye bahut zaroori hai

`site_config.json` file ko Notepad/VS Code mein kholo:

- `base_url`: actual live address daalo, trailing slash ke saath; example `https://factblogger-abc.pages.dev/` — apna real URL use karna.
- `contact_email`: apna working email address daalo.
- `google_site_verification`: Search Console token baad mein mile to add karo; abhi blank reh sakta hai.
- `adsense_publisher_id` blank rakho aur `adsense_auto_ads_enabled` false rakho jab tak Google account mein publisher ID aur review instructions na mil jaayein.

Save karne ke baad:

```powershell
py build_site.py
py check_site.py
git add site_config.json public
git commit -m "Configure FactBlogger live website"
git push
```

**Placeholder URL ke saath deploy mat chhodna.** Jab tak real URL set nahi hota, builder jaan-boojhkar pages par `noindex` aur `robots.txt` mein crawl block banata hai taaki galat URL Google mein na jaaye.

## 3. Google Search Console

1. https://search.google.com/search-console/about kholo.
2. URL-prefix property add karo aur exact live HTTPS URL daalo.
3. HTML meta-tag verification choose karoge to Google token `site_config.json` ke `google_site_verification` field mein paste karo. Rebuild/push karo, phir Search Console mein Verify click karo.
4. **Indexing → Sitemaps** mein `sitemap.xml` submit karo.
5. URL Inspection mein homepage aur 2–3 genuine article URLs check karo. Zaroorat ho to **Request indexing** use karo. Request se indexing guarantee nahi hoti.

## 4. AI se article drafts aur photos

1. https://ollama.com/download/windows se Ollama install karo.
2. PowerShell mein run karo: `ollama pull qwen2.5:3b`.
3. Example:

```powershell
py generate_post.py --topic "How to use AI tools responsibly for college projects" --category "AI & Technology" --language en --source-url "https://developers.google.com/search/docs/fundamentals/using-gen-ai-content"
```

4. Draft `drafts/` folder mein banega. Ye live publish nahi hoga.
5. Har fact/source, originality, Hindi/English translation, image relevance, image license, credit aur alt text manually verify karo.
6. Approval ke baad hi publish command chalao:

```powershell
py publish_post.py YOUR-DRAFT-FILENAME.json --push
```

`--push` tabhi use karo jab GitHub/Cloudflare deployment set ho chuka ho. `daily_draft.bat` ko Windows Task Scheduler se schedule kiya ja sakta hai; PC on hona aur Ollama chalna zaroori hai. Default workflow drafts banata hai, har article ko automatically live nahi karta.

## 5. AdSense approval ke liye detailed checklist

`ADSENSE_APPROVAL_GUIDE_HINDI.md` padho. Usmein policy, privacy page, original content, Search Console, site ownership verification, AdSense code, `ads.txt`, review status aur rejection ke baad improvements ke steps hain.

Yaad rahe: koi fixed post count, word count, AI model, SEO plugin, ya site code AdSense approval guarantee nahi karta. Google original helpful content, policies, navigation, trust aur user experience review karta hai. Approval ke baad hi actual ad serving shuru honi chahiye.
