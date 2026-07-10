"""
research_company.py — Scraping de datos de empresa + guardado. DETERMINÍSTICO.

La síntesis (armar el brief estructurado) la hace Claude Code en la conversación
— NO consume Anthropic API tokens.

Flujo:
1. `--scrape` baja el texto crudo del sitio de la empresa + Google News y lo imprime/guarda.
2. Yo (Claude Code) leo ese texto y redacto el research estructurado en Markdown.
3. `--save` guarda mi research en output/companies/<company>/research.md y lo registra en Sheets.

Uso:
  python core/research_company.py --scrape --company "Acme" --url "https://acme.com" --output .tmp/acme_raw.json
  python core/research_company.py --save --company "Acme" --url "https://acme.com" --md-file .tmp/acme_research.md --add-to-sheets
"""

import argparse
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup

OUTPUT_DIR = Path("output/companies")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def safe_name(company: str) -> str:
    return re.sub(r"[^a-z0-9\-]", "", company.lower().replace(" ", "-"))


def scrape_url(url: str, timeout: int = 15) -> str:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        return re.sub(r"\s+", " ", text)[:5000]
    except Exception as e:
        return f"[Error scraping {url}: {e}]"


def get_company_urls(company: str, company_url: str) -> list:
    base = company_url.rstrip("/")
    encoded = requests.utils.quote(f'"{company}"')
    return [
        (base, "Homepage"),
        (f"{base}/about", "About"),
        (f"{base}/careers", "Careers"),
        (f"{base}/blog", "Blog"),
        (f"https://news.google.com/search?q={encoded}&hl=en", "Google News"),
    ]


def scrape_company_data(company: str, company_url: str) -> dict:
    raw_data = {}
    for url, label in get_company_urls(company, company_url):
        print(f"  Scraping {label}: {url}", file=sys.stderr)
        content = scrape_url(url)
        if not content.startswith("[Error"):
            raw_data[label] = content
        time.sleep(1.0)
    return raw_data


def save_research(company: str, research_md: str, url: str = "") -> Path:
    company_dir = OUTPUT_DIR / safe_name(company)
    company_dir.mkdir(parents=True, exist_ok=True)

    # Encabezado con metadata si el md no lo trae
    if not research_md.lstrip().startswith("# "):
        header = f"# Research: {company}\n\n**URL:** {url}  \n**Fecha:** {date.today().isoformat()}\n\n---\n\n"
        research_md = header + research_md

    research_path = company_dir / "research.md"
    research_path.write_text(research_md, encoding="utf-8")
    print(f"Research guardado: {research_path}")
    return research_path


def add_to_sheets(company: str, company_url: str, research_path: Path,
                  industry: str = "", size: str = ""):
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from tools.sheets_manager import add_company_research
    add_company_research(
        company=company, industry=industry, size=size,
        website=company_url, drive_url=str(research_path),
        notes=f"Research local: {research_path}",
    )


def main():
    parser = argparse.ArgumentParser(description="Scraping + guardado de research de empresa")
    parser.add_argument("--scrape", action="store_true", help="Baja el texto crudo de la empresa")
    parser.add_argument("--save", action="store_true", help="Guarda el research sintetizado por Claude Code")
    parser.add_argument("--company", required=True, help="Nombre de la empresa")
    parser.add_argument("--url", default="", help="URL del sitio oficial")
    parser.add_argument("--output", help="[scrape] Ruta de salida del JSON crudo (default: stdout)")
    parser.add_argument("--md-file", help="[save] Ruta al research Markdown redactado por Claude Code")
    parser.add_argument("--industry", default="", help="[save] Industria")
    parser.add_argument("--size", default="", help="[save] Tamaño de la empresa")
    parser.add_argument("--add-to-sheets", action="store_true", help="[save] Registra en Google Sheets")
    args = parser.parse_args()

    if args.scrape:
        if not args.url:
            print("Error: --scrape requiere --url")
            sys.exit(1)
        print(f"Scrapeando {args.company}...", file=sys.stderr)
        raw_data = scrape_company_data(args.company, args.url)
        if not raw_data:
            print("No se pudo obtener información. Verificá la URL.", file=sys.stderr)
            sys.exit(1)
        payload = json.dumps(raw_data, ensure_ascii=False, indent=2)
        if args.output:
            out = Path(args.output)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(payload, encoding="utf-8")
            print(f"Texto crudo ({len(raw_data)} fuentes) → {out}", file=sys.stderr)
            print("Ahora sintetizo el research en la conversación y lo guardo con --save.", file=sys.stderr)
        else:
            print(payload)

    elif args.save:
        if not args.md_file:
            print("Error: --save requiere --md-file (el research redactado por Claude Code)")
            sys.exit(1)
        research_md = Path(args.md_file).read_text(encoding="utf-8")
        research_path = save_research(args.company, research_md, args.url)
        if args.add_to_sheets:
            add_to_sheets(args.company, args.url, research_path, args.industry, args.size)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
