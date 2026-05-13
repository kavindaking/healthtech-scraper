# Longevity & Health-Tech Content Engine

Two things in one package:
1. A **news scraper** that pulls the latest health/longevity stories from research databases, industry press, and consumer-brand mentions
2. A **video playbook** for turning that news into short-form content

---

## Part 1 — The Scraper

### What it does
Each time you run it, the scraper:
- Pulls peer-reviewed papers from **PubMed** (last 3 days)
- Pulls preprints from **bioRxiv**
- Pulls articles from **STAT, Endpoints, Fierce Biotech, FDA, NIH, Nature Aging, Science Daily, MedCity News**
- Searches **Google News** for every consumer brand in your watchlist (Rythm, Create Wellness, Superpower, Function Health, Levels, Whoop, Oura, Bryan Johnson, etc.)
- Scores each item by keyword relevance, dedupes near-duplicates, and outputs two files:
  - `output/news_YYYY-MM-DD.json` — machine-readable, pipe into anything
  - `output/digest_YYYY-MM-DD.html` — open in your browser, looks like a newspaper

### Setup (one time)
```bash
pip install feedparser requests
```

### Run it
```bash
python scraper.py
```

Then open `output/digest_YYYY-MM-DD.html` in your browser.

### Schedule it (so it runs every morning)
**Mac/Linux** — add to crontab:
```
0 7 * * * cd /path/to/scraper && /usr/bin/python3 scraper.py
```

**Windows** — use Task Scheduler, point it at `python scraper.py`.

### Customizing — edit `config.json`
No code changes needed for any of this:

- **`consumer_brands`** — add or remove brand names. Anything in this list gets a Google News search every run. Add competitors as you find them.
- **`longevity_keywords`** — what counts as "on-topic." Each match adds 1 to the item's score.
- **`high_priority_keywords`** — things like "FDA approval," "Phase 3," "Series B." Each match adds 3. These items float to the top.
- **`rss_feeds`** — add any blog or news site with an RSS feed. To check: try appending `/feed` or `/rss` to the site's URL.
- **`pubmed_queries`** — PubMed query syntax. The `last 3 days[dp]` filter is added automatically.
- **`settings.days_to_look_back`** — change from 3 to 7 for a weekly digest.
- **`settings.min_score_for_digest`** — raise to 3 or 4 if you're getting too much noise.

### How scoring works
- Every general longevity keyword match: **+1**
- Every high-priority keyword (FDA, funding, Phase 3 etc.): **+3**
- Every consumer brand mentioned: **+2**
- Items from brand-specific Google News searches get a baseline of **2** so they always show up

The digest groups items into four buckets: **High priority** (score ≥ 5), **Consumer brands**, **Research**, **Industry news**.

### Adding email delivery later
The JSON output is ready to pipe anywhere. Easiest path:
```python
# top of a new send_email.py
import json, smtplib
from email.mime.text import MIMEText
items = json.load(open("output/news_2026-05-14.json"))
html = open("output/digest_2026-05-14.html").read()
# ...standard SMTP send
```
Or pipe to a service like Resend, Postmark, or even Zapier's "Webhook → Gmail" recipe.

### Notes on what this *won't* catch
- Instagram posts (Instagram blocks scrapers, period — you'd need their official Graph API)
- Twitter/X posts (similar — needs paid API access now)
- Podcast episodes (could be added — most podcasts have RSS feeds)

If you want podcast tracking added, the architecture supports it — just add the podcast RSS feeds to `config.json` under `rss_feeds`.

---

## Part 2 — Video Style Playbook

Since the source profile is on Instagram and I can't read it directly, this is the general playbook for **"data-driven health explainer"** content that performs well on Reels/TikTok/Shorts. Tune to taste once you see what's working for you.

### The 60-second formula
1. **Hook (0–3 sec)** — the surprising stat, the counterintuitive claim, or the question that makes someone stop scrolling.
   - "A new study found that taking creatine *changes your DNA expression*."
   - "This $400 blood test is replacing your annual physical — and the doctors are nervous."
2. **The setup (3–10 sec)** — what's the context? Who ran the study, who launched the product, what were they trying to do?
3. **The finding (10–40 sec)** — what they actually found, with one or two specific numbers on screen. Numbers > adjectives.
4. **The catch (40–55 sec)** — every study has limitations; every product has trade-offs. Naming them builds trust and gives commenters something to argue about (engagement).
5. **The takeaway (55–60 sec)** — what should the viewer do, think, or wait for? End on a clean line that invites a save or share.

### The visual recipe
- Talking head, vertical, centered.
- Burned-in captions, big, with the keywords colored. Tools: CapCut, Submagic, Opus Clip.
- B-roll on every "fact" beat: study screenshot, product hero shot, a graph. Keep cuts at 1.5–2.5 seconds.
- One consistent lower-third with your name and a topic tag.
- Avoid stock footage for the main beats — original screen recordings and study screenshots feel more credible.

### Picking your stance
The "data-driven" angle works best when you commit to one identity:
- **The Translator** — turns dense papers into plain English without picking sides
- **The Skeptic** — calls out hype, dunks on bad studies, defends evidence
- **The Early-Adopter** — tests the products, shares results, picks winners
- **The Hype-Sorter** — for each new thing, gives a clear "worth it / skip / wait" verdict

The Skeptic and Hype-Sorter angles tend to grow fastest because they create contrast and discussion. The Translator angle grows slower but builds the most trust over time.

### Topic mix that works
Roughly aim for:
- **40% research news** — pulled from the scraper's PubMed and bioRxiv outputs
- **30% product/company news** — from the consumer-brands section
- **20% myth-busting / evergreen** — "is creatine actually safe," "what ApoB really measures"
- **10% personal** — your own labs, routine, what you're testing

### Workflow that pairs with the scraper
1. Run scraper each morning over coffee
2. Open the HTML digest, scan top 10 items
3. Pick **one** with a hook you find genuinely surprising — if you're not surprised, your viewer won't be
4. Click through to the original source. **Read the actual paper or press release, never just the headline.** This is the difference between trusted creators and the ones that get ratio'd.
5. Draft script: hook, setup, finding, catch, takeaway. 100–150 words total.
6. Film, caption, post. Aim for 3–5x per week.

### What to track
Don't chase views; chase **saves** and **comments**. Saves mean "this was useful enough to come back to" — the strongest signal for serious health content. Comments mean you said something with a stance.

---

## Files in this package
- `scraper.py` — the scraper itself
- `config.json` — your watchlist, keywords, sources (edit this)
- `README.md` — this file
- `output/` — created on first run; holds the daily JSON + HTML

Questions or want to extend it (email delivery, Slack webhook, podcast tracking, Notion sync)? The architecture is modular — each source is a separate function in `scraper.py`.
