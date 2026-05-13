#!/usr/bin/env python3
"""
Longevity & Health-Tech News Scraper
-------------------------------------
Pulls the latest news from:
  - PubMed (peer-reviewed research)
  - bioRxiv / medRxiv (preprints)
  - RSS feeds (STAT, Endpoints, Fierce Biotech, FDA, NIH, Nature Aging, etc.)
  - Google News RSS queries (for consumer brand mentions: Rythm, Create, Superpower, etc.)

Scores each item by keyword relevance, dedupes, and writes:
  - news_<date>.json   (machine-readable)
  - digest_<date>.html (open in your browser)

Usage:
  pip install feedparser requests
  python scraper.py
"""

import json
import re
import time
import html
import hashlib
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from difflib import SequenceMatcher

import requests
import feedparser


CONFIG_PATH = Path(__file__).parent / "config.json"
OUTPUT_DIR = Path(__file__).parent / "output"


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def clean_text(s: str) -> str:
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)  # strip HTML tags
    s = html.unescape(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def make_id(url: str, title: str) -> str:
    return hashlib.md5(f"{url}|{title}".encode()).hexdigest()[:12]


def parse_date(s):
    """Best-effort date parsing -> aware datetime in UTC."""
    if not s:
        return None
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            continue
    return None


# -----------------------------------------------------------------------------
# Sources
# -----------------------------------------------------------------------------

def fetch_rss(feed_url: str, source_name: str, cfg: dict):
    """Generic RSS pull."""
    items = []
    try:
        headers = {"User-Agent": cfg["settings"]["user_agent"]}
        r = requests.get(feed_url, headers=headers,
                         timeout=cfg["settings"]["request_timeout_seconds"])
        feed = feedparser.parse(r.content)
        for entry in feed.entries[:cfg["settings"]["max_items_per_source"]]:
            published = parse_date(entry.get("published") or entry.get("updated"))
            items.append({
                "source": source_name,
                "source_type": "rss",
                "title": clean_text(entry.get("title", "")),
                "url": entry.get("link", ""),
                "summary": clean_text(entry.get("summary", ""))[:600],
                "published": published.isoformat() if published else None,
            })
    except Exception as e:
        print(f"  ! RSS error ({source_name}): {e}")
    return items


def fetch_pubmed(query: str, cfg: dict):
    """PubMed E-utilities — search then fetch summaries."""
    items = []
    lookback_days = cfg["settings"]["days_to_look_back"]
    try:
        # Step 1: esearch
        params = {
            "db": "pubmed",
            "term": f"({query}) AND last {lookback_days} days[dp]",
            "retmax": cfg["settings"]["max_items_per_source"],
            "retmode": "json",
            "sort": "date",
        }
        r = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            params=params,
            timeout=cfg["settings"]["request_timeout_seconds"],
        )
        ids = r.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return items

        # Step 2: esummary
        params = {"db": "pubmed", "id": ",".join(ids), "retmode": "json"}
        r = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
            params=params,
            timeout=cfg["settings"]["request_timeout_seconds"],
        )
        result = r.json().get("result", {})
        for pmid in ids:
            doc = result.get(pmid)
            if not doc:
                continue
            items.append({
                "source": f"PubMed: {query[:40]}",
                "source_type": "pubmed",
                "title": clean_text(doc.get("title", "")),
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "summary": f"Journal: {doc.get('fulljournalname', '')} | "
                           f"Authors: {', '.join(a.get('name', '') for a in doc.get('authors', [])[:3])}",
                "published": parse_date(doc.get("pubdate", "")).isoformat()
                              if parse_date(doc.get("pubdate", "")) else None,
            })
        time.sleep(0.4)  # be polite to NCBI
    except Exception as e:
        print(f"  ! PubMed error ({query[:40]}): {e}")
    return items


def fetch_biorxiv(cfg: dict):
    """bioRxiv recent preprints API."""
    items = []
    try:
        lookback = cfg["settings"]["days_to_look_back"]
        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=lookback)
        url = f"https://api.biorxiv.org/details/biorxiv/{start}/{end}/0"
        r = requests.get(url, timeout=cfg["settings"]["request_timeout_seconds"])
        data = r.json()
        wanted_cats = [c.lower() for c in cfg["biorxiv_categories"]]
        for paper in data.get("collection", [])[:cfg["settings"]["max_items_per_source"] * 2]:
            if paper.get("category", "").lower() not in wanted_cats:
                continue
            items.append({
                "source": "bioRxiv",
                "source_type": "preprint",
                "title": clean_text(paper.get("title", "")),
                "url": f"https://www.biorxiv.org/content/10.1101/{paper.get('doi', '').split('/')[-1]}",
                "summary": clean_text(paper.get("abstract", ""))[:600],
                "published": paper.get("date"),
            })
    except Exception as e:
        print(f"  ! bioRxiv error: {e}")
    return items


def fetch_brand_news(brand: str, cfg: dict):
    """Google News RSS for a brand name. Catches press releases & coverage."""
    q = urllib.parse.quote(f'"{brand}"')
    url = f"https://news.google.com/rss/search?q={q}+when:7d&hl=en-US&gl=US&ceid=US:en"
    items = fetch_rss(url, f"Brand: {brand}", cfg)
    for it in items:
        it["brand"] = brand
    return items


# -----------------------------------------------------------------------------
# Scoring & dedup
# -----------------------------------------------------------------------------

def score_item(item: dict, cfg: dict) -> int:
    text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
    score = 0
    matched_keywords = []

    for kw in cfg["longevity_keywords"]:
        if kw.lower() in text:
            score += 1
            matched_keywords.append(kw)

    for kw in cfg["high_priority_keywords"]:
        if kw.lower() in text:
            score += 3
            matched_keywords.append(kw)

    for brand in cfg["consumer_brands"]:
        if brand.lower() in text:
            score += 2
            matched_keywords.append(brand)

    # Brand-feed items get a baseline so they show up even without keyword hits
    if item.get("source_type") == "rss" and item.get("brand"):
        score = max(score, 2)

    item["score"] = score
    item["matched"] = matched_keywords
    return score


def dedupe(items):
    """Remove duplicates by URL and by fuzzy title match."""
    seen_urls = set()
    seen_titles = []
    out = []
    for it in items:
        url = it.get("url", "")
        title = it.get("title", "").lower()
        if not title:
            continue
        if url in seen_urls:
            continue
        is_dup = False
        for prev in seen_titles:
            if SequenceMatcher(None, title, prev).ratio() > 0.85:
                is_dup = True
                break
        if is_dup:
            continue
        seen_urls.add(url)
        seen_titles.append(title)
        out.append(it)
    return out


# -----------------------------------------------------------------------------
# Output
# -----------------------------------------------------------------------------

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Longevity Digest — {date}</title>
<style>
  :root {{
    --bg: #faf8f3;
    --ink: #1a1a1a;
    --muted: #6b6b6b;
    --accent: #c1440e;
    --rule: #d4cfc2;
    --card: #ffffff;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 0;
    background: var(--bg);
    color: var(--ink);
    font-family: Georgia, 'Iowan Old Style', serif;
    line-height: 1.55;
  }}
  .wrap {{ max-width: 780px; margin: 0 auto; padding: 60px 32px 80px; }}
  header {{ border-bottom: 2px solid var(--ink); padding-bottom: 24px; margin-bottom: 40px; }}
  .kicker {{
    font-family: 'Helvetica Neue', sans-serif;
    text-transform: uppercase;
    letter-spacing: 0.18em;
    font-size: 11px;
    color: var(--accent);
    font-weight: 700;
  }}
  h1 {{ font-size: 44px; margin: 8px 0 4px; letter-spacing: -0.02em; }}
  .date {{ color: var(--muted); font-style: italic; }}
  .stats {{ font-family: 'Helvetica Neue', sans-serif; font-size: 13px; color: var(--muted); margin-top: 12px; }}
  h2.section {{
    font-family: 'Helvetica Neue', sans-serif;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-size: 13px;
    color: var(--accent);
    border-bottom: 1px solid var(--rule);
    padding-bottom: 8px;
    margin-top: 48px;
  }}
  article {{
    background: var(--card);
    border: 1px solid var(--rule);
    padding: 20px 24px;
    margin: 16px 0;
    border-radius: 2px;
  }}
  article h3 {{ margin: 0 0 8px; font-size: 20px; line-height: 1.3; }}
  article h3 a {{ color: var(--ink); text-decoration: none; }}
  article h3 a:hover {{ color: var(--accent); }}
  .meta {{
    font-family: 'Helvetica Neue', sans-serif;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--muted);
    margin-bottom: 10px;
  }}
  .meta .score {{
    color: var(--accent);
    font-weight: 700;
    margin-right: 8px;
  }}
  .summary {{ color: #333; font-size: 15px; }}
  .tags {{ margin-top: 10px; }}
  .tag {{
    display: inline-block;
    font-family: 'Helvetica Neue', sans-serif;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    background: #f0ebde;
    color: var(--accent);
    padding: 3px 8px;
    margin: 2px 4px 2px 0;
    border-radius: 2px;
  }}
  footer {{ margin-top: 60px; padding-top: 24px; border-top: 1px solid var(--rule);
            font-family: 'Helvetica Neue', sans-serif; font-size: 12px; color: var(--muted); }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="kicker">Longevity & Health-Tech Digest</div>
    <h1>The Latest</h1>
    <div class="date">{date_long}</div>
    <div class="stats">{total} items · {hi_count} high-priority · {brand_count} brand mentions</div>
  </header>
  {body}
  <footer>
    Generated by your local scraper. Edit <code>config.json</code> to change sources, brands, or keywords.
  </footer>
</div>
</body>
</html>
"""


def render_html(items, cfg):
    now = datetime.now()
    grouped = {"High priority": [], "Consumer brands": [], "Research": [], "Industry news": []}

    for it in items:
        if it["score"] >= 5:
            grouped["High priority"].append(it)
        elif it.get("brand") or any(b.lower() in (it.get("title") or "").lower()
                                    for b in cfg["consumer_brands"]):
            grouped["Consumer brands"].append(it)
        elif it["source_type"] in ("pubmed", "preprint"):
            grouped["Research"].append(it)
        else:
            grouped["Industry news"].append(it)

    body_parts = []
    for section, group_items in grouped.items():
        if not group_items:
            continue
        body_parts.append(f'<h2 class="section">{section} ({len(group_items)})</h2>')
        for it in group_items[:20]:
            tags = "".join(f'<span class="tag">{html.escape(t)}</span>'
                           for t in it.get("matched", [])[:6])
            body_parts.append(f"""
            <article>
              <div class="meta"><span class="score">★ {it['score']}</span> {html.escape(it['source'])} · {html.escape(it.get('published', '')[:10] if it.get('published') else 'undated')}</div>
              <h3><a href="{html.escape(it.get('url', '#'))}" target="_blank">{html.escape(it['title'])}</a></h3>
              <div class="summary">{html.escape(it.get('summary', '')[:400])}</div>
              <div class="tags">{tags}</div>
            </article>
            """)

    return HTML_TEMPLATE.format(
        date=now.strftime("%Y-%m-%d"),
        date_long=now.strftime("%A, %B %d, %Y"),
        total=len(items),
        hi_count=len(grouped["High priority"]),
        brand_count=len(grouped["Consumer brands"]),
        body="\n".join(body_parts) or "<p>No items matched today.</p>",
    )


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main():
    cfg = load_config()
    OUTPUT_DIR.mkdir(exist_ok=True)
    all_items = []

    print("→ Fetching RSS feeds…")
    for feed in cfg["rss_feeds"]:
        print(f"  · {feed['name']}")
        all_items.extend(fetch_rss(feed["url"], feed["name"], cfg))

    print("→ Fetching PubMed…")
    for q in cfg["pubmed_queries"]:
        print(f"  · {q[:60]}")
        all_items.extend(fetch_pubmed(q, cfg))

    print("→ Fetching bioRxiv preprints…")
    all_items.extend(fetch_biorxiv(cfg))

    print("→ Fetching consumer brand mentions…")
    for brand in cfg["consumer_brands"]:
        print(f"  · {brand}")
        all_items.extend(fetch_brand_news(brand, cfg))
        time.sleep(0.2)

    print(f"\n→ Got {len(all_items)} raw items. Scoring + deduping…")
    for it in all_items:
        score_item(it, cfg)

    min_score = cfg["settings"]["min_score_for_digest"]
    filtered = [it for it in all_items if it["score"] >= min_score]
    filtered = dedupe(filtered)
    filtered.sort(key=lambda x: (-x["score"], x.get("published") or ""), reverse=False)
    filtered.sort(key=lambda x: -x["score"])

    print(f"→ {len(filtered)} items after dedup & scoring.")

    date_str = datetime.now().strftime("%Y-%m-%d")
    json_path = OUTPUT_DIR / f"news_{date_str}.json"
    html_path = OUTPUT_DIR / f"digest_{date_str}.html"

    with open(json_path, "w") as f:
        json.dump(filtered, f, indent=2)
    with open(html_path, "w") as f:
        f.write(render_html(filtered, cfg))

    print(f"\n✓ Wrote {json_path}")
    print(f"✓ Wrote {html_path}")
    print(f"\nOpen the HTML file in your browser to read the digest.")


if __name__ == "__main__":
    main()
