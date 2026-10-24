# FactBlogger — Google AdSense Approval Guide (Hindi/Hinglish)

**Goal:** Website ko technically ready, transparent, useful aur Google review ke liye eligible banana. Is guide se approval guarantee nahi hota; final decision Google ka hota hai.

## Phase 1 — Brand, ownership and contact

- [ ] Site name `FactBlogger` consistent hai.
- [ ] Live website HTTPS par open hoti hai, broken links nahi hain.
- [ ] `site_config.json` mein `base_url` exact live origin hai, trailing slash ke saath. Path/query nahi hona chahiye.
- [ ] `contact_email` ek email hai jise owner actually read karta hai.
- [ ] About page sach batata hai ki site kaun chalata hai, kya cover karti hai, aur AI ka use kaise hota hai. Apna real author/editor name ya accurate editorial identity add karo; koi fake credentials mat likho.
- [ ] Contact page par working email/contact method hai.
- [ ] Privacy Policy actual tools ke mutabiq update ki gayi hai—Cloudflare hosting, analytics (agar use ho), cookies, ads aur third-party embeds. Generic text ko bina review kiye final legal advice mat samjho.
- [ ] Disclaimer aur Editorial Policy available hain.
- [ ] Navigation, mobile view, image display, category pages aur 404 page check kiye gaye hain.
- [ ] Koi construction/placeholder text, fake review, fake stats, fake author, copied page, broken menu ya empty category intentionally publish nahi ki gayi.

## Phase 2 — Content quality (sabse important)

Google koi universal minimum article count ya word count publish nahi karta jo approval guarantee kare. Isliye number chase karne ke bajaye niche-focused content ko substantially improve karo.

Har article ke liye:

- [ ] Specific user question ka complete, accurate jawab ho.
- [ ] Article mein original explanation, examples, screenshots, tests, comparisons, code, useful checklist ya genuine editorial insight ho—sirf sources ka paraphrase na ho.
- [ ] Important changing claims official/primary sources se fact-check kiye gaye hon.
- [ ] Source links article ke claims ko support karte hon; invented citations nahi.
- [ ] AI se likhe hue errors, repetitive filler, keyword stuffing aur fake first-person experience remove kiye gaye hon.
- [ ] Title, meta description aur H1 page ke exact topic ko accurately describe karte hon.
- [ ] Image relevant ho; licence/permission commercial use allow karti ho; attribution/credit aur alt text sahi ho.
- [ ] Article ki language natural ho. Hindi aur English versions duplicate pages na hon; har version intended audience ke liye useful aur edited ho.
- [ ] Related articles ke internal links hon; unrelated pages ko zabardasti link na karo.
- [ ] Author/editor identity, publish/update date and correction route clear hon where appropriate.
- [ ] Article substantially redundant ya copied na ho; website par search engines ko dikhane ke liye hi hundreds of low-value pages na banao.

**Practical editorial target (Google rule nahi):** Pehle kuch hafton mein har core category ke andar multiple genuinely useful articles taiyar karo. Current starter bundle ke 5 articles launch examples hain; unko khud review karke update karo aur jab tak depth, sources, originality aur experience achhe na hon, approval-ready assume mat karo.

## Phase 3 — Configure and test SEO

1. `site_config.json` ka `base_url` real live URL set karo.
2. Apna email configure karo.
3. Run:

   ```powershell
   py build_site.py
   py check_site.py
   ```

4. Output folder `public/` ko local preview karo, then deploy.
5. Check live URLs:
   - `/`
   - `/categories/`
   - har category archive
   - `/about/`, `/contact/`, `/privacy-policy/`, `/disclaimer/`, `/editorial-policy/`
   - at least 3 useful article URLs
   - `/robots.txt`, `/sitemap.xml`, `/rss.xml`, `/404.html`
6. Confirm `robots.txt` par `Disallow: /` nahi hai aur normal pages par `noindex,nofollow` nahi hai. This project intentionally uses noindex until real `base_url` is configured.
7. Canonical URLs correct site origin ko point karte hon; localhost/placeholder ya kisi aur site's URL na ho.

## Phase 4 — Google Search Console setup (free)

1. Open https://search.google.com/search-console/about .
2. Add a **URL-prefix** property with your exact deployed HTTPS origin (example shape: `https://your-project.pages.dev/`).
3. Choose HTML tag verification if convenient. Copy only the verification token into `google_site_verification` in `site_config.json`. Do not paste the whole `<meta>` tag—only the `content` token.
4. Run `py build_site.py`; commit and deploy updated `public/`.
5. View the live homepage source and check that `google-site-verification` exists. Then click Verify in Search Console.
6. Open **Indexing → Sitemaps** and submit `sitemap.xml`.
7. Use URL Inspection on homepage and each important article. Resolve any blocked resources, wrong canonical, redirect, `noindex`, or server errors; request indexing after meaningful fixes.
8. Review **Pages/Indexing** and **Performance** regularly. Search Console's discovery or indexing is not guaranteed, even with a valid sitemap.

## Phase 5 — Apply for AdSense

1. Review current terms and eligibility at https://support.google.com/adsense/answer/9724 and https://support.google.com/adsense/answer/7299563 . You must meet the current eligibility rules (including minimum age) and site policies.
2. Create/sign in to the AdSense account using accurate information that matches the site owner/payee requirements. Avoid duplicate accounts if Google rules prohibit them.
3. In AdSense, open **Sites → New site** and enter the exact site address accepted by the interface.
4. Google will provide a site verification method. Follow the exact method displayed in the account (code snippet, ads.txt or meta-tag method depending on the workflow).
5. If Google gives you a publisher ID of the form `ca-pub-################`, put that exact ID in `adsense_publisher_id` in `site_config.json`. Never guess or use another person's publisher ID.
6. To load the standard AdSense script across the generated pages, set `adsense_auto_ads_enabled` to `true`, run `py build_site.py`, preview the source, and deploy. Only do this when the account's instructions call for the code to be present. The builder creates `ads.txt` for a valid publisher ID.
7. Check the deployed source: the AdSense script should reference your ID; `/ads.txt` should contain a line like `google.com, PUBLISHER_NUMBER, DIRECT, f08c47fec0942fa0` using the actual numeric part provided by the publisher ID.
8. Return to AdSense and request/complete the review. Wait for the status shown in the account. Google says site checks often take a few days but may take longer (sometimes 2–4 weeks); use the current account status rather than assuming a deadline.
9. Ads should only be served after the site becomes eligible/ready. Do not place dummy ads or manually simulate clicks.

**Free subdomain caveat:** Start with the free hosting subdomain to keep development costs down, but do not assume every AdSense account/site flow will accept or verify that exact host. Test it in AdSense. If Google requires a domain you control for the chosen setup, a custom domain may cost money. This project cannot guarantee approval for a `pages.dev` subdomain or any other domain.

## Phase 6 — Privacy, ads and ongoing compliance

- Keep the Privacy Policy accurate about Google ads, cookies, analytics, embedded media and contact data actually used.
- Follow consent requirements that apply to your audience and Google products (for example, special consent requirements may apply when serving users in the EEA/UK/Switzerland).
- Never click your own ads, ask friends/readers to click ads, buy bots/traffic, hide ads behind buttons, or encourage accidental clicks.
- Do not publish copyrighted content, scraped news, unlicensed images, deceptive pages, or large batches of repetitive AI articles created mainly to manipulate rankings.
- Review the current Google Publisher Policies and Search spam policies as these can change.
- Keep a regular content correction/update process and monitor Search Console.

## If AdSense rejects the website

1. Open the exact reason/status in AdSense; don't guess the reason.
2. Check `robots.txt`, `noindex`, sitemap and homepage availability.
3. Fix policy problems, thin/duplicated pages, missing contact/policy information, broken navigation or poor mobile experience.
4. Improve the articles that provide little original value; remove or noindex genuinely low-value duplicate pages until improved.
5. Re-test live URLs and `ads.txt`, then request review again if the account offers that option.

## Official sources

- AdSense site readiness: https://support.google.com/adsense/answer/7299563
- AdSense eligibility: https://support.google.com/adsense/answer/9724
- AdSense site management: https://support.google.com/adsense/answer/12131223
- Add a site in AdSense: https://support.google.com/adsense/answer/12169212
- Google Search generative AI content guidance: https://developers.google.com/search/docs/fundamentals/using-gen-ai-content
- Google Search spam policies: https://developers.google.com/search/docs/essentials/spam-policies
- Search Console sitemap guidance: https://developers.google.com/search/docs/crawling-indexing/sitemaps/overview
