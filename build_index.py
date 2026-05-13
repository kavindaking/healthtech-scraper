#!/usr/bin/env python3
"""
Build an index.html that lists every daily digest, newest first.
Runs after the scraper in the GitHub Actions workflow.
"""

import json
import html
from datetime import datetime
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "output"


def collect_digests():
    """Find all digest HTML files and pair them with their JSON metadata."""
    digests = []
    for html_file in sorted(OUTPUT_DIR.glob("digest_*.html"), reverse=True):
        date_str = html_file.stem.replace("digest_", "")
        json_file = OUTPUT_DIR / f"news_{date_str}.json"

        item_count = 0
        hi_count = 0
        brand_count = 0
        if json_file.exists():
            try:
                data = json.loads(json_file.read_text())
                item_count = len(data)
                hi_count = sum(1 for d in data if d.get("score", 0) >= 5)
                brand_count = sum(1 for d in data if d.get("brand"))
            except Exception:
                pass

        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            date_pretty = date_obj.strftime("%A, %B %d, %Y")
        except Exception:
            date_pretty = date_str

        digests.append({
            "date": date_str,
            "date_pretty": date_pretty,
            "filename": html_file.name,
            "items": item_count,
            "high_priority": hi_count,
            "brands": brand_count,
        })
    return digests


INDEX_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Longevity & Health-Tech Digest — Archive</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

  :root {{
    --bg: #0f1117;
    --surface: #1a1d27;
    --surface-hover: #222632;
    --border: #2a2e3a;
    --ink: #e4e4e7;
    --muted: #8b8d98;
    --accent: #c1440e;
    --accent-soft: rgba(193, 68, 14, 0.12);
    --accent-glow: rgba(193, 68, 14, 0.25);
    --green: #34d399;
    --blue: #60a5fa;
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    background: var(--bg);
    color: var(--ink);
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    line-height: 1.6;
    min-height: 100vh;
  }}

  .bg-grid {{
    position: fixed;
    inset: 0;
    background-image:
      linear-gradient(rgba(255,255,255,0.015) 1px, transparent 1px),
      linear-gradient(90deg, rgba(255,255,255,0.015) 1px, transparent 1px);
    background-size: 60px 60px;
    pointer-events: none;
    z-index: 0;
  }}

  .wrap {{
    position: relative;
    z-index: 1;
    max-width: 800px;
    margin: 0 auto;
    padding: 60px 24px 100px;
  }}

  header {{
    text-align: center;
    margin-bottom: 56px;
  }}

  .kicker {{
    display: inline-block;
    text-transform: uppercase;
    letter-spacing: 0.2em;
    font-size: 11px;
    font-weight: 600;
    color: var(--accent);
    background: var(--accent-soft);
    padding: 6px 16px;
    border-radius: 100px;
    margin-bottom: 20px;
  }}

  h1 {{
    font-size: clamp(32px, 5vw, 48px);
    font-weight: 700;
    letter-spacing: -0.03em;
    line-height: 1.15;
    margin-bottom: 12px;
    background: linear-gradient(135deg, #fff 0%, #a0a0a8 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }}

  .subtitle {{
    color: var(--muted);
    font-size: 15px;
    max-width: 500px;
    margin: 0 auto;
  }}

  .digest-list {{
    display: flex;
    flex-direction: column;
    gap: 12px;
  }}

  .digest-card {{
    display: flex;
    align-items: center;
    gap: 20px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px 24px;
    text-decoration: none;
    color: var(--ink);
    transition: all 0.2s ease;
    position: relative;
    overflow: hidden;
  }}

  .digest-card::before {{
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, var(--accent-glow) 0%, transparent 60%);
    opacity: 0;
    transition: opacity 0.3s ease;
  }}

  .digest-card:hover {{
    background: var(--surface-hover);
    border-color: var(--accent);
    transform: translateY(-2px);
    box-shadow: 0 8px 32px rgba(0,0,0,0.3), 0 0 0 1px var(--accent-glow);
  }}

  .digest-card:hover::before {{
    opacity: 1;
  }}

  .date-badge {{
    position: relative;
    z-index: 1;
    flex-shrink: 0;
    width: 56px;
    height: 56px;
    background: var(--accent-soft);
    border: 1px solid rgba(193, 68, 14, 0.2);
    border-radius: 10px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    line-height: 1;
  }}

  .date-badge .day {{
    font-size: 22px;
    font-weight: 700;
    color: var(--accent);
  }}

  .date-badge .month {{
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--accent);
    opacity: 0.8;
    margin-top: 2px;
  }}

  .card-body {{
    position: relative;
    z-index: 1;
    flex: 1;
    min-width: 0;
  }}

  .card-title {{
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 4px;
  }}

  .card-stats {{
    display: flex;
    gap: 16px;
    font-size: 12px;
    color: var(--muted);
  }}

  .stat {{
    display: flex;
    align-items: center;
    gap: 4px;
  }}

  .stat .dot {{
    width: 6px;
    height: 6px;
    border-radius: 50%;
    flex-shrink: 0;
  }}

  .dot.total {{ background: var(--blue); }}
  .dot.hi {{ background: var(--accent); }}
  .dot.brand {{ background: var(--green); }}

  .card-arrow {{
    position: relative;
    z-index: 1;
    flex-shrink: 0;
    color: var(--muted);
    font-size: 18px;
    transition: transform 0.2s ease, color 0.2s ease;
  }}

  .digest-card:hover .card-arrow {{
    transform: translateX(4px);
    color: var(--accent);
  }}

  .empty {{
    text-align: center;
    padding: 60px 20px;
    color: var(--muted);
  }}

  .empty p {{ font-size: 15px; }}

  footer {{
    margin-top: 60px;
    padding-top: 24px;
    border-top: 1px solid var(--border);
    text-align: center;
    font-size: 12px;
    color: var(--muted);
  }}

  @media (max-width: 600px) {{
    .wrap {{ padding: 40px 16px 60px; }}
    .digest-card {{ padding: 16px; gap: 14px; }}
    .card-stats {{ flex-wrap: wrap; gap: 10px; }}
  }}
</style>
</head>
<body>
<div class="bg-grid"></div>
<div class="wrap">
  <header>
    <div class="kicker">Daily Archive</div>
    <h1>Longevity &amp; Health-Tech Digest</h1>
    <p class="subtitle">Automated daily intelligence from PubMed, bioRxiv, industry press, and consumer brand tracking.</p>
  </header>

  {body}

  <footer>
    Auto-generated daily by GitHub Actions · Edit <code>config.json</code> to customize sources &amp; keywords
  </footer>
</div>
</body>
</html>
"""


def build_card(d):
    try:
        dt = datetime.strptime(d["date"], "%Y-%m-%d")
        day = dt.strftime("%d").lstrip("0")
        month = dt.strftime("%b")
    except Exception:
        day = "?"
        month = "?"

    return f"""
    <a class="digest-card" href="{html.escape(d['filename'])}">
      <div class="date-badge">
        <span class="day">{day}</span>
        <span class="month">{month}</span>
      </div>
      <div class="card-body">
        <div class="card-title">{html.escape(d['date_pretty'])}</div>
        <div class="card-stats">
          <span class="stat"><span class="dot total"></span>{d['items']} items</span>
          <span class="stat"><span class="dot hi"></span>{d['high_priority']} high-priority</span>
          <span class="stat"><span class="dot brand"></span>{d['brands']} brand mentions</span>
        </div>
      </div>
      <span class="card-arrow">→</span>
    </a>
    """


def main():
    digests = collect_digests()

    if digests:
        cards = "\n".join(build_card(d) for d in digests)
        body = f'<div class="digest-list">\n{cards}\n</div>'
    else:
        body = '<div class="empty"><p>No digests yet. The first one will appear after the scraper runs.</p></div>'

    index_html = INDEX_TEMPLATE.format(body=body)
    out_path = OUTPUT_DIR / "index.html"
    out_path.write_text(index_html)
    print(f"✓ Wrote {out_path}")


if __name__ == "__main__":
    main()
