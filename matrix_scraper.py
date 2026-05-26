"""
Matrix.se veckoannons-scraper med lokal OCR via LM Studio eller Ollama.

Hämtar veckans annonsbilder från matrix.se, OCR:ar dem med en lokal
vision-modell via en OpenAI-kompatibel server (LM Studio på localhost:1234
eller Ollama på localhost:11434) och skriver strukturerad JSON.

Allt sker på din dator — ingen molntjänst, ingen API-nyckel.

Beroenden: requests
Förutsättningar:
  - Python 3.10+
  - LM Studio (rekommenderat eftersom du redan har det) ELLER Ollama
  - En vision-modell laddad. Förslag:
        Qwen2.5-VL-7B-Instruct       (bäst OCR, ~5-7GB VRAM)
        Llama-3.2-11B-Vision         (~7-8GB VRAM)
        MiniCPM-V-2.6                (lätt och snabb, ~5GB)

Konfiguration via miljövariabler (alla har vettiga defaultvärden):
  OCR_BASE_URL    "http://localhost:1234/v1"   (LM Studio)
                   eller "http://localhost:11434/v1" (Ollama)
  OCR_MODEL       modellens namn så som det visas i servern
  OCR_TIMEOUT     sekunder per bild (default 300)
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import requests


# ---------- Konfiguration ----------

BASE_URL = "https://www.matrix.se/erbjudande"
# Annonsbildernas URL-mönster på matrix.se. De fyra bilderna 0-3 är "veckans annons".
# Justera range om Matrix utökar antalet annonser per vecka.
IMAGE_URL_TEMPLATE = "https://go.mat-rix.se/public/convertedks-{i}.jpg"
IMAGE_INDICES = range(0, 4)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

# Server-konfiguration.
# Default = Ollama native API (mest pålitligt för community-modeller som openbmb/*).
# För LM Studio: sätt OCR_BASE_URL=http://localhost:1234/v1 (OpenAI-bridge används då).
OCR_BASE_URL = os.environ.get("OCR_BASE_URL", "http://localhost:11434")
OCR_MODEL = os.environ.get("OCR_MODEL", "openbmb/minicpm-v4.5")
OCR_TIMEOUT = int(os.environ.get("OCR_TIMEOUT", "600"))
# Auto-detektera API-stil: /v1 i URL = OpenAI-kompatibel, annars Ollama native
USE_OPENAI_API = OCR_BASE_URL.rstrip("/").endswith("/v1")
# API-nyckel krävs inte av lokala servrar — vi skickar en dummy.
OCR_API_KEY = os.environ.get("OCR_API_KEY", "ollama")

PROJECT_ROOT = Path(__file__).resolve().parent
IMAGES_DIR = PROJECT_ROOT / "images"
HISTORY_DIR = PROJECT_ROOT / "history"
LOG_FILE = PROJECT_ROOT / "scraper.log"
LATEST_JSON = PROJECT_ROOT / "prices.json"


# ---------- Logging ----------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("matrix")


# ---------- Hjälpfunktioner ----------


def iso_week_tag(now: dt.datetime) -> str:
    iso = now.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def build_image_urls() -> list[str]:
    """Returnerar de hårdkodade URL:erna för veckans annonser."""
    urls = [IMAGE_URL_TEMPLATE.format(i=i) for i in IMAGE_INDICES]
    log.info("Försöker hämta %d annonsbilder", len(urls))
    return urls


def download_image(url: str, dest: Path) -> Path | None:
    """Laddar ner bilden, returnerar None vid 404."""
    log.info("Laddar ner %s", url)
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60)
    if r.status_code == 404:
        log.info("  -> 404 (annonsen finns inte denna vecka), hoppar över")
        return None
    r.raise_for_status()
    dest.write_bytes(r.content)
    log.info("  -> %s (%d bytes)", dest.name, len(r.content))
    return dest


def guess_media_type(path: Path) -> str:
    ext = path.suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(ext, "image/jpeg")


# ---------- OCR via OpenAI-kompatibel server ----------

OCR_PROMPT = """Du är en OCR-motor för svenska livsmedelsannonser från butikskedjan Matrix.
Läs av bilden noggrant och returnera ENDAST giltig JSON enligt schemat nedan —
ingen kodblockmarkering, ingen omkringliggande text, bara JSON.

Schema:
{
  "ad_title": "övergripande rubrik (t.ex. VECKANS ANNONS) eller null",
  "validity": "giltighetsperiod (t.ex. v. 22) eller null",
  "products": [
    {
      "name": "produktnamn",
      "brand": "varumärke eller null",
      "price": 79.90,
      "currency": "SEK",
      "unit": "kg/st/förp/l/hg eller null",
      "comparison_price": null,
      "comparison_unit": null,
      "campaign_note": "ev. begränsning som 'Max 3/kund' eller null",
      "raw_text": "fullständig text kring produkten precis som den står"
    }
  ]
}

Regler:
- Lämna fält som null om värdet inte syns tydligt. Gissa inte.
- Priser i kronor som tal: 79.90, inte "79:90".
- Stora siffror + upphöjda ören kombineras: 39 + 90 = 39.90.
- Skilj på pris (stort) och jämförpris/jmf-pris (mindre, t.ex. kr/kg).
- Lista ALLA produkter i bilden.
- Behåll svenska tecken (åäö).
- Svara med endast JSON-objektet, ingenting annat."""


def ocr_image(image_path: Path) -> dict[str, Any]:
    log.info("OCR (%s): %s", OCR_MODEL, image_path.name)
    img_b64 = base64.standard_b64encode(image_path.read_bytes()).decode("ascii")

    if USE_OPENAI_API:
        data_url = f"data:{guess_media_type(image_path)};base64,{img_b64}"
        url = f"{OCR_BASE_URL.rstrip('/')}/chat/completions"
        payload = {
            "model": OCR_MODEL,
            "temperature": 0.1,
            "max_tokens": 4096,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": OCR_PROMPT},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {OCR_API_KEY}",
            "Content-Type": "application/json",
        }
    else:
        # Ollama native API — robustare för community-vision-modeller (openbmb/*)
        url = f"{OCR_BASE_URL.rstrip('/')}/api/chat"
        payload = {
            "model": OCR_MODEL,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1, "num_ctx": 8192},
            "messages": [
                {
                    "role": "user",
                    "content": OCR_PROMPT,
                    "images": [img_b64],
                }
            ],
        }
        headers = {"Content-Type": "application/json"}

    try:
        r = requests.post(url, json=payload, headers=headers, timeout=OCR_TIMEOUT)
        r.raise_for_status()
    except requests.RequestException as e:
        log.error("OCR-anrop misslyckades: %s", e)
        return {"_error": f"ocr_request_failed: {e}", "products": []}

    try:
        body = r.json()
        if USE_OPENAI_API:
            response_text = body["choices"][0]["message"]["content"].strip()
        else:
            response_text = body["message"]["content"].strip()
    except (KeyError, IndexError, ValueError) as e:
        log.error("Oväntat svarformat: %s — rått: %s", e, r.text[:400])
        return {"_error": f"bad_response_format: {e}", "products": []}

    if not response_text.startswith("{"):
        first = response_text.find("{")
        last = response_text.rfind("}")
        if first != -1 and last != -1 and last > first:
            response_text = response_text[first : last + 1]

    try:
        return json.loads(response_text)
    except json.JSONDecodeError as e:
        log.error("Kunde inte parsa JSON: %s — rått: %s", e, response_text[:500])
        return {
            "_parse_error": str(e),
            "_raw": response_text,
            "products": [],
        }


def _normalize_model_name(name: str) -> str:
    """Strippa ':latest'-suffix för tolerant matchning."""
    return name[:-7] if name.endswith(":latest") else name


def check_server() -> bool:
    """Kontrollera att servern svarar och listar modellen."""
    if USE_OPENAI_API:
        list_url = f"{OCR_BASE_URL.rstrip('/')}/models"
    else:
        list_url = f"{OCR_BASE_URL.rstrip('/')}/api/tags"

    try:
        r = requests.get(list_url, timeout=5)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        log.error(
            "Når inte OCR-servern på %s (%s).\n"
            "Ollama: kontrollera att tjänsten kör (Ollama-ikonen i system tray, eller 'ollama serve').\n"
            "LM Studio: starta servern i Developer-fliken.",
            OCR_BASE_URL,
            e,
        )
        return False
    except ValueError:
        log.error("Servern svarade men inte med JSON. URL korrekt? (%s)", OCR_BASE_URL)
        return False

    if USE_OPENAI_API:
        models = [m.get("id", "") for m in data.get("data", [])]
    else:
        models = [m.get("name", "") for m in data.get("models", [])]

    target = _normalize_model_name(OCR_MODEL)
    available_normalized = {_normalize_model_name(m) for m in models}

    if not models:
        log.warning("Servern listar inga modeller. Ladda en vision-modell först.")
    elif target not in available_normalized:
        log.warning(
            "Modellen '%s' finns inte i serverns lista. Tillgängliga: %s\n"
            "(Försöker ändå — modellnamn kan skilja sig från id.)",
            OCR_MODEL,
            ", ".join(models),
        )
    else:
        log.info("OCR-server OK. Modell: %s", OCR_MODEL)
    return True


# ---------- Huvudflöde ----------


def main() -> int:
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)

    if not check_server():
        return 2

    now = dt.datetime.now().astimezone()
    week_tag = iso_week_tag(now)

    urls = build_image_urls()

    ads: list[dict[str, Any]] = []
    for url in urls:
        url_hash = hashlib.sha1(url.encode()).hexdigest()[:8]
        original_name = url.rsplit("/", 1)[-1]
        local_name = f"{week_tag}_{url_hash}_{original_name}"
        local_path = IMAGES_DIR / local_name

        try:
            if local_path.exists():
                log.info("Bilden finns redan: %s", local_path.name)
            else:
                result = download_image(url, local_path)
                if result is None:
                    # 404 — annonsen finns inte den här veckan
                    continue
        except requests.RequestException as e:
            log.error("Misslyckades ladda ner %s: %s", url, e)
            continue

        ocr_result = ocr_image(local_path)
        ads.append(
            {
                "source_url": url,
                "local_path": str(local_path.relative_to(PROJECT_ROOT)),
                **ocr_result,
            }
        )

    output = {
        "scraped_at": now.isoformat(),
        "iso_week": week_tag,
        "source_page": BASE_URL,
        "image_urls_tried": list(urls),
        "ocr_backend": OCR_BASE_URL,
        "ocr_model": OCR_MODEL,
        "ad_count": len(ads),
        "ads": ads,
    }

    LATEST_JSON.write_text(
        json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    history_path = HISTORY_DIR / f"prices_{week_tag}.json"
    history_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    total_products = sum(len(a.get("products", [])) for a in ads)
    log.info(
        "Klart. %d annonser, %d produkter totalt. Skrev %s och %s",
        len(ads),
        total_products,
        LATEST_JSON.name,
        history_path.name,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
