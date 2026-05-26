# Matrix.se veckoannons-scraper (lokal OCR)

Hämtar veckans annonser från [matrix.se/erbjudande](https://www.matrix.se/erbjudande), OCR:ar bilderna med en lokal vision-modell via Ollama (kör på din RTX 3060) och skriver strukturerad JSON med produkter, priser, enheter och jämförpriser.

Allt sker på din dator — ingen molntjänst, ingen API-nyckel, inga kostnader.

## Filer

- `matrix_scraper.py` — själva scrapern
- `requirements.txt` — Python-beroenden (bara `requests`)
- `run.bat` — det Task Scheduler kör varje vecka (modellnamnet sätts här)
- `prices.json` — senaste resultat
- `history/prices_YYYY-Www.json` — arkiverat per ISO-vecka
- `images/` — nerladdade annonsbilder
- `scraper.log` — körlogg

## Engångs-setup

### 1. Python + requests

Installera Python 3.10+ från [python.org/downloads](https://www.python.org/downloads/) (kryssa i "Add Python to PATH"). Installera sedan beroendet:

```powershell
pip install requests
```

### 2. Ollama + vision-modell

Hämta Ollama från [ollama.com/download](https://ollama.com/download). Installera — den körs som tjänst i bakgrunden på `localhost:11434`.

Hämta en vision-modell. Rekommendation för RTX 3060 8GB:

```powershell
ollama pull openbmb/minicpm-v4.5
```

MiniCPM-V 4.5 (8B params, byggd på Qwen3 + SigLIP2) är best-in-class på OCR bland små öppna modeller. Alternativ:

```powershell
ollama pull qwen2.5vl:7b           # Stark generalistisk vision
ollama pull llama3.2-vision:11b    # Större men svagare på text-OCR
ollama pull openbmb/minicpm-v4.6   # 1.3B, sjukt snabb men sämre OCR
```

> Byt modell genom att redigera raden `set "OCR_MODEL=..."` överst i `run.bat`.

### 3. Provkör

Kontrollera först att Ollama svarar och har modellen:

```powershell
ollama list
```

Kör sedan:

```powershell
cd S:\Documents\Claude\Projects\Vadskajaghandla
.\run.bat
```

Första bilden tar 30–90s (modell laddas i VRAM). Efter det går varje bild på 10–30s. Var inte rädd att vänta — avbryt inte med Ctrl+C första gången.

När körningen är klar finns `prices.json` i mappen + en kopia i `history\`.

## Veckoschema i Windows Task Scheduler

1. `Win + R` → `taskschd.msc` → Enter
2. Högerpanelen → **"Create Basic Task..."**
3. **Namn:** `Matrix veckopriser`
4. **Trigger:** Weekly. T.ex. måndag 08:00.
5. **Action:** Start a program.
   - **Program/script:** `S:\Documents\Claude\Projects\Vadskajaghandla\run.bat`
   - **Start in (optional):** `S:\Documents\Claude\Projects\Vadskajaghandla`
6. Bocka i **"Open the Properties dialog when I click Finish"**, klicka **Finish**.
7. I Properties:
   - **General → "Run whether user is logged on or not"** om det ska köra utan att du är inloggad
   - **Conditions** → avbocka "Start the task only if the computer is on AC power" (för laptops)
   - **Settings** → bocka i "Run task as soon as possible after a scheduled start is missed"

Testkör med högerklick → **Run**.

> **Viktigt:** Ollama måste vara igång när tasken körs. Den startas normalt automatiskt med Windows. Verifiera med `Get-Service -Name "Ollama*"` i PowerShell, eller kolla att Ollama-ikonen finns i system tray.

## Vill du köra LM Studio istället?

Sätt två miljövariabler innan körning:

```powershell
setx OCR_BASE_URL "http://localhost:1234/v1"
setx OCR_MODEL "qwen2.5-vl-7b-instruct"
```

Starta LM Studios server från Developer-fliken med modellen laddad. Allt annat fungerar likadant.

## JSON-struktur

```json
{
  "scraped_at": "2026-05-26T08:00:12+02:00",
  "iso_week": "2026-W22",
  "source_page": "https://www.matrix.se/erbjudande",
  "ocr_backend": "http://localhost:11434",
  "ocr_model": "openbmb/minicpm-v4.5",
  "ad_count": 3,
  "ads": [
    {
      "source_url": "https://go.mat-rix.se/public/convertedks-0.jpg",
      "local_path": "images/2026-W22_abcd1234_convertedks-0.jpg",
      "ad_title": "VECKANS ANNONS",
      "validity": "gäller v.22",
      "products": [
        {
          "name": "Kycklingfilé",
          "brand": "Kronfågel",
          "price": 79.90,
          "currency": "SEK",
          "unit": "kg",
          "comparison_price": null,
          "comparison_unit": null,
          "campaign_note": "Max 2 kg/kund",
          "raw_text": "Kycklingfilé Kronfågel 79:90 kr/kg Max 2 kg/kund"
        }
      ]
    }
  ]
}
```

## Felsökning

- **"Når inte OCR-servern"** — Ollama är inte igång. Kontrollera Ollama-ikonen i system tray eller kör `ollama serve` i en terminal.
- **"Modellen X finns inte"** — kör `ollama pull openbmb/minicpm-v4.5` (eller motsvarande). Verifiera med `ollama list`.
- **404 från `/v1/chat/completions`** — community-modeller (`openbmb/*`) hanteras ibland inte av OpenAI-bridgen. Scriptet använder Ollamas native `/api/chat` som default — kontrollera att `OCR_BASE_URL` *inte* slutar med `/v1`.
- **Långsamma första anrop** — modellen läses in i VRAM första gången, kan ta upp till 90s. Avbryt inte med Ctrl+C. Höj `OCR_TIMEOUT` i `run.bat` om det fortfarande timeoutar.
- **Felaktiga priser i JSON** — testa en starkare modell (`qwen2.5vl:7b` eller `qwen2.5vl:32b`). Större modeller spiller till RAM på 8GB-kort men funkar.
- **Loggar** — se `scraper.log` (UTF-8).
- **Inga bilder hittas på sidan** — matrix.se kan ha bytt URL-mönster. Justera `IMAGE_HOST_PATTERN` i `matrix_scraper.py`.
