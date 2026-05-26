"""
Genererar en HTML-vy av prices.json och öppnar den i standardwebbläsaren.

Kör: python view_prices.py
"""

from __future__ import annotations

import html
import json
import sys
import webbrowser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
PRICES_JSON = PROJECT_ROOT / "prices.json"
OUTPUT_HTML = PROJECT_ROOT / "prices.html"


def fmt(value) -> str:
    if value is None or value == "":
        return "—"
    return html.escape(str(value))


def fmt_price(value) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.2f} kr".replace(".", ",")
    except (TypeError, ValueError):
        return html.escape(str(value))


def fmt_comparison(price, unit) -> str:
    if price is None:
        return "—"
    try:
        s = f"{float(price):.2f}".replace(".", ",")
    except (TypeError, ValueError):
        return html.escape(str(price))
    if unit:
        return f"{s} kr/{html.escape(str(unit))}"
    return f"{s} kr"


def render(data: dict) -> str:
    ads = data.get("ads", [])
    total_products = sum(len(a.get("products", [])) for a in ads)

    rows_html: list[str] = []
    for ad_idx, ad in enumerate(ads, 1):
        ad_title = fmt(ad.get("ad_title") or f"Annons {ad_idx}")
        validity = ad.get("validity")
        local_path = ad.get("local_path")
        source_url = ad.get("source_url", "")

        # Header per annons
        header_meta = []
        if validity:
            header_meta.append(f"Giltighet: {fmt(validity)}")
        if source_url:
            header_meta.append(
                f'<a href="{html.escape(source_url)}" target="_blank">Källa</a>'
            )
        if local_path:
            header_meta.append(
                f'<a href="{html.escape(local_path)}" target="_blank">Bild</a>'
            )
        meta = " · ".join(header_meta)

        thumb = ""
        if local_path:
            thumb = (
                f'<a href="{html.escape(local_path)}" target="_blank">'
                f'<img src="{html.escape(local_path)}" alt="annonsbild" '
                f'class="thumb" /></a>'
            )

        products = ad.get("products", [])
        if not products:
            err = ad.get("_error") or ad.get("_parse_error")
            empty = (
                f'<tr><td colspan="6" class="empty">'
                f'Inga produkter extraherade{" – " + html.escape(str(err)) if err else ""}.'
                f"</td></tr>"
            )
            rows_html.append(empty)
            continue

        product_rows = []
        for p in products:
            campaign = p.get("campaign_note")
            brand = p.get("brand")
            name_cell = f"<strong>{fmt(p.get('name'))}</strong>"
            if brand:
                name_cell += f'<div class="brand">{fmt(brand)}</div>'
            if campaign:
                name_cell += f'<div class="campaign">{fmt(campaign)}</div>'
            unit = p.get("unit")
            unit_str = f"per {html.escape(str(unit))}" if unit else ""
            price_cell = (
                f'<span class="price">{fmt_price(p.get("price"))}</span>'
                f'<div class="unit">{unit_str}</div>' if unit_str
                else f'<span class="price">{fmt_price(p.get("price"))}</span>'
            )
            compare_cell = fmt_comparison(
                p.get("comparison_price"), p.get("comparison_unit")
            )
            raw = p.get("raw_text") or ""
            raw_cell = (
                f'<details><summary>Visa text</summary>'
                f'<div class="raw">{fmt(raw)}</div></details>'
                if raw else "—"
            )
            product_rows.append(
                f"<tr>"
                f"<td>{name_cell}</td>"
                f"<td>{price_cell}</td>"
                f"<td>{compare_cell}</td>"
                f"<td>{raw_cell}</td>"
                f"</tr>"
            )

        rows_html.append(
            f"""
            <section class="ad">
              <div class="ad-head">
                {thumb}
                <div class="ad-meta">
                  <h2>{ad_title}</h2>
                  <div class="sub">{meta}</div>
                </div>
              </div>
              <table>
                <thead>
                  <tr><th>Produkt</th><th>Pris</th><th>Jämförpris</th><th>Råtext</th></tr>
                </thead>
                <tbody>
                  {"".join(product_rows)}
                </tbody>
              </table>
            </section>
            """
        )

    body = "\n".join(rows_html) or "<p>Inga annonser i prices.json.</p>"

    return f"""<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="utf-8">
<title>Matrix veckopriser — {fmt(data.get('iso_week'))}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    margin: 0;
    padding: 2rem;
    background: #f6f7f9;
    color: #1a1a1a;
  }}
  header.page {{
    max-width: 1100px;
    margin: 0 auto 2rem;
  }}
  header.page h1 {{
    margin: 0 0 .25rem;
    font-size: 1.6rem;
  }}
  header.page .meta {{
    color: #666;
    font-size: .9rem;
  }}
  section.ad {{
    max-width: 1100px;
    margin: 0 auto 2rem;
    background: white;
    border-radius: 12px;
    box-shadow: 0 1px 3px rgba(0,0,0,.08);
    overflow: hidden;
  }}
  .ad-head {{
    display: flex;
    gap: 1rem;
    padding: 1rem 1.25rem;
    align-items: flex-start;
    border-bottom: 1px solid #eee;
  }}
  .thumb {{
    width: 140px;
    height: auto;
    border-radius: 6px;
    border: 1px solid #ddd;
    display: block;
  }}
  .ad-meta h2 {{
    margin: 0 0 .25rem;
    font-size: 1.15rem;
  }}
  .ad-meta .sub {{
    color: #666;
    font-size: .85rem;
  }}
  .ad-meta a {{
    color: #2563eb;
    text-decoration: none;
  }}
  .ad-meta a:hover {{ text-decoration: underline; }}
  table {{
    width: 100%;
    border-collapse: collapse;
  }}
  th, td {{
    padding: .65rem 1rem;
    text-align: left;
    vertical-align: top;
    border-bottom: 1px solid #f0f0f0;
  }}
  th {{
    background: #fafafa;
    font-weight: 600;
    font-size: .85rem;
    color: #555;
    text-transform: uppercase;
    letter-spacing: .03em;
  }}
  tr:last-child td {{ border-bottom: none; }}
  .price {{
    font-weight: 600;
    font-size: 1.05rem;
    color: #b91c1c;
  }}
  .unit {{
    font-size: .8rem;
    color: #888;
  }}
  .brand {{
    font-size: .85rem;
    color: #555;
  }}
  .campaign {{
    display: inline-block;
    margin-top: .25rem;
    padding: .1rem .5rem;
    background: #fef3c7;
    color: #92400e;
    border-radius: 4px;
    font-size: .75rem;
  }}
  .empty {{
    color: #888;
    font-style: italic;
    text-align: center;
  }}
  details summary {{
    cursor: pointer;
    color: #2563eb;
    font-size: .85rem;
  }}
  .raw {{
    margin-top: .25rem;
    padding: .5rem;
    background: #f9fafb;
    border-radius: 4px;
    font-family: ui-monospace, "SF Mono", Menlo, monospace;
    font-size: .8rem;
    white-space: pre-wrap;
  }}
  footer {{
    max-width: 1100px;
    margin: 0 auto;
    color: #888;
    font-size: .8rem;
    text-align: center;
  }}
</style>
</head>
<body>
<header class="page">
  <h1>Matrix veckopriser — {fmt(data.get('iso_week'))}</h1>
  <div class="meta">
    {len(ads)} annonser · {total_products} produkter ·
    Skrapad {fmt(data.get('scraped_at'))} ·
    Modell: {fmt(data.get('ocr_model'))}
  </div>
</header>
{body}
<footer>
  Genererad från prices.json av view_prices.py
</footer>
</body>
</html>
"""


def main() -> int:
    open_browser = "--open" in sys.argv[1:]

    if not PRICES_JSON.exists():
        print(f"Hittar inte {PRICES_JSON}. Kör run.bat först.", file=sys.stderr)
        return 1

    try:
        data = json.loads(PRICES_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"Kunde inte parsa {PRICES_JSON}: {e}", file=sys.stderr)
        return 2

    html_doc = render(data)
    OUTPUT_HTML.write_text(html_doc, encoding="utf-8")
    print(f"Skrev {OUTPUT_HTML}")
    if open_browser:
        webbrowser.open(OUTPUT_HTML.as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
