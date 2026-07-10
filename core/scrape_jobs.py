"""
scrape_jobs.py — Scraping de LinkedIn vía el endpoint público "guest" (requests + BS4).
Uso: python core/scrape_jobs.py --source linkedin --keywords "automation engineer" --save
     python core/scrape_jobs.py --keywords "automation engineer,AI ops" --save --add-to-sheets
"""

import argparse
import hashlib
import json
import random
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
# Importing env_config loads data/credentials/.env (then a root .env).
from env_config import linkedin_location as env_linkedin_location, target_region
from location_filters import REGION_CHOICES, filter_by_region, normalize_region

HEADERS_BASE = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

# Repo root = one level up from core/. Paths below are resolved against it, NOT
# against the current working directory: these modules are imported in-process
# by `api/jobs/handlers/*`, where the CWD is wherever uvicorn happened to start.
_ROOT = Path(__file__).resolve().parent.parent

CONFIG_PATH = _ROOT / "config" / "job_sites.json"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        print(f"Error: {CONFIG_PATH} no encontrado.")
        sys.exit(1)
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def random_delay(min_ms: int, max_ms: int):
    time.sleep(random.uniform(min_ms / 1000, max_ms / 1000))


def normalize_position(source: str, company: str, role: str, url: str,
                        location: str = "Remote", salary: str = "",
                        description: str = "", remote: bool = True,
                        tipo: str = "full-time", tags: list = None) -> dict:
    return {
        "source": source,
        "tipo": tipo,
        "company": company.strip(),
        "role": role.strip(),
        "url": url.strip(),
        "location": location.strip() or "Remote",
        "remote": remote,
        "salary": salary.strip(),
        "description": description[:3000],
        "tags": tags or [],
        "date_posted": "",
    }


def dedup(positions: list) -> list:
    seen = set()
    unique = []
    for p in positions:
        raw = f"{p['company'].lower()}-{p['role'].lower()}"
        key = re.sub(r"[^a-z0-9\-]", "", raw.replace(" ", "-"))
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


# ─── LinkedIn (guest endpoint, sin Playwright) ────────────────

# LinkedIn expone un endpoint público "guest" que devuelve el HTML de las
# tarjetas de empleo sin login ni JS. Es más rápido y estable que renderizar
# la SPA con Playwright. Pagina de a 25 con el parámetro `start`.
# Se rate-limitea (HTTP 429) tras ~10 páginas por IP; para nuestro volumen alcanza.
LINKEDIN_GUEST_URL = (
    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
)
# Endpoint guest para el detalle de UNA vacante (trae la descripción completa,
# que las tarjetas de la búsqueda no incluyen). {job_id} es el ID numérico.
LINKEDIN_JOB_DETAIL_URL = (
    "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
)
LINKEDIN_PAGE_SIZE = 25
# Cache local de descripciones por job_id: una vacante se pide UNA sola vez en la
# vida, aunque aparezca bajo varias keywords o en corridas de distintos días.
# Lives under data/ because it holds scraped job descriptions — user content,
# which hard rule #1 confines to data/. It used to be a CWD-relative `.tmp/`
# path, which both escaped that rule and silently moved with the server's CWD.
LI_DESC_CACHE_PATH = _ROOT / "data" / "cache" / "li_desc_cache.json"


def _linkedin_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS_BASE)
    session.headers.update({
        "Referer": "https://www.linkedin.com/jobs/search/",
        "X-Requested-With": "XMLHttpRequest",
    })
    return session


def _prime_session(session) -> None:
    """GET la página real de búsqueda para setear cookies de invitado (bcookie,
    lidc). Las llamadas al endpoint guest con esas cookies tienen un techo de
    rate más alto → menos 429. Best-effort: si falla, seguimos igual."""
    try:
        session.get("https://www.linkedin.com/jobs/search/", timeout=15)
    except requests.RequestException:
        pass


def _load_desc_cache() -> dict:
    try:
        return json.loads(LI_DESC_CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_desc_cache(cache: dict) -> None:
    try:
        LI_DESC_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        LI_DESC_CACHE_PATH.write_text(
            json.dumps(cache, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass


def _extract_job_id(card, job_url: str) -> str:
    """El ID numérico de la vacante, para pedir su descripción. Preferimos el
    `data-entity-urn` de la tarjeta; si falta, caemos al final de la URL."""
    urn = card.get("data-entity-urn", "") or ""
    match = re.search(r"(\d{6,})", urn)
    if match:
        return match.group(1)
    match = re.search(r"(\d{6,})", job_url)
    return match.group(1) if match else ""


def fetch_linkedin_description(session, job_id: str, timeout: int = 20):
    """Trae la descripción de una vacante. Retorna (texto, status_http, retry_after).
    texto=None ante error de red; status=429 señala rate limit; retry_after es el
    header `Retry-After` en segundos si LinkedIn lo envía (si no, None)."""
    url = LINKEDIN_JOB_DETAIL_URL.format(job_id=job_id)
    try:
        resp = session.get(url, timeout=timeout)
    except requests.RequestException:
        return None, None, None
    if resp.status_code == 429:
        raw = resp.headers.get("Retry-After")
        try:
            retry_after = int(raw) if raw else None
        except ValueError:
            retry_after = None
        return None, 429, retry_after
    if resp.status_code != 200:
        return "", resp.status_code, None
    soup = BeautifulSoup(resp.text, "html.parser")
    node = (soup.select_one(".show-more-less-html__markup")
            or soup.select_one(".description__text"))
    if not node:
        return "", 200, None
    return node.get_text(separator="\n", strip=True), 200, None


def enrich_linkedin_descriptions(positions: list, existing_desc_ids: set = None,
                                 max_retries: int = 2) -> list:
    """Segunda pasada: por cada vacante conservada, pide su descripción al
    endpoint de detalle. Se corre DESPUÉS del filtro geo + dedup para no gastar
    requests en vacantes descartadas. Cuatro palancas anti-429:

    ① dedup-vs-Sheets — no pide descripción de vacantes que ya están en el
       tracker CON descripción (`existing_desc_ids`); re-correr un search casi
       no gasta requests de detalle.
    ② cache local por job_id — una descripción ya vista no se vuelve a pedir,
       aunque aparezca bajo otra keyword o en otra corrida.
    ③ priming de cookies — sube el techo de rate antes de empezar.
    ④ backoff adaptativo — ante 429 espera (respetando `Retry-After`) y
       reintenta; solo corta la pasada si el 429 persiste tras los reintentos.
    """
    existing_desc_ids = existing_desc_ids or set()
    cache = _load_desc_cache()

    make_id = None
    if existing_desc_ids:
        try:
            from sheets_manager import make_position_id as make_id
        except Exception:
            make_id = None  # sin id-maker no dedupeamos contra Sheets, seguimos

    session = _linkedin_session()
    _prime_session(session)  # ③

    fetched = from_cache = skipped_tracked = 0
    stopped = False
    for pos in positions:
        job_id = pos.pop("_job_id", "")
        if stopped or not job_id or pos.get("description"):
            continue

        # ① ya trackeada con descripción → no gastamos request
        if make_id is not None:
            pid = make_id(pos.get("company", ""), pos.get("role", ""))
            if pid in existing_desc_ids:
                skipped_tracked += 1
                continue

        # ② cache local
        if job_id in cache:
            pos["description"] = cache[job_id][:3000]
            from_cache += 1
            continue

        # ④ fetch con backoff adaptativo
        text = None
        for attempt in range(max_retries + 1):
            text, status, retry_after = fetch_linkedin_description(session, job_id)
            if status == 429:
                if attempt < max_retries:
                    wait = retry_after if retry_after else (2 ** attempt) * 2 + random.uniform(0, 1.5)
                    print(f"[LinkedIn] 429 (intento {attempt + 1}/{max_retries + 1}); "
                          f"backoff {wait:.1f}s...")
                    time.sleep(wait)
                    continue
                print("[LinkedIn] 429 persistente. Corto el enriquecimiento; el "
                      "resto de las vacantes conserva su metadata.")
                stopped = True
                text = None
            break

        if stopped:
            continue
        if text:
            pos["description"] = text[:3000]
            cache[job_id] = text[:3000]
            fetched += 1
        random_delay(1200, 2800)

    # Limpieza: ninguna vacante debe quedar con el campo interno _job_id.
    for pos in positions:
        pos.pop("_job_id", None)
    _save_desc_cache(cache)
    print(f"[LinkedIn] Descripciones — {fetched} nuevas, {from_cache} de cache, "
          f"{skipped_tracked} ya en Sheets | {len(positions)} vacantes")
    return positions


def scrape_linkedin(keywords: str, max_pages: int = 3,
                    linkedin_location: str = None) -> list:
    # LinkedIn wants a geography NAME, not a country code. Falls back to
    # LINKEDIN_LOCATION from the env ("Worldwide" if unset) rather than to any
    # one country — the caller's market is configuration, not a constant.
    linkedin_location = linkedin_location or env_linkedin_location()
    print(f"[LinkedIn] Buscando: {keywords} | location={linkedin_location}")
    positions = []

    session = _linkedin_session()
    _prime_session(session)  # cookies de invitado → menos 429 en la paginación

    for page_num in range(max_pages):
        start = page_num * LINKEDIN_PAGE_SIZE
        params = {
            "keywords": keywords,
            "location": linkedin_location,
            "f_WT": "2,3",         # Remote + Hybrid (antes solo "2" = Remote)
            "f_TPR": "r2592000",   # últimos ~30 días (antes r604800 = 7 días)
            "start": start,
        }
        print(f"[LinkedIn] Página {page_num + 1} (start={start})...")

        try:
            resp = session.get(LINKEDIN_GUEST_URL, params=params, timeout=20)
        except requests.RequestException as e:
            print(f"[LinkedIn] Error HTTP: {e}")
            break

        if resp.status_code == 429:
            print("[LinkedIn] Rate limit (429). Cortando; esperá ~30 min y reintentá.")
            break
        if resp.status_code != 200:
            print(f"[LinkedIn] HTTP {resp.status_code}. Cortando.")
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select("li div.base-card, li div.job-search-card, div.base-card")
        if not cards:
            print("[LinkedIn] Sin más resultados en esta página.")
            break

        jobs_found = 0
        for card in cards:
            title_el = card.select_one("h3.base-search-card__title")
            company_el = card.select_one("h4.base-search-card__subtitle a, h4.base-search-card__subtitle")
            location_el = card.select_one(".job-search-card__location")
            link_el = card.select_one("a.base-card__full-link, a[href*='/jobs/view/']")
            date_el = card.select_one("time")

            role = title_el.get_text(strip=True) if title_el else ""
            company = company_el.get_text(strip=True) if company_el else ""
            location = location_el.get_text(strip=True) if location_el else "Remote"
            job_url = link_el.get("href", "").split("?")[0] if link_el else ""

            if role and job_url:
                pos = normalize_position(
                    source="linkedin",
                    company=company or "Unknown",
                    role=role,
                    url=job_url,
                    location=location,
                )
                if date_el and date_el.get("datetime"):
                    pos["date_posted"] = date_el.get("datetime")
                # ID interno para la 2ª pasada de descripciones (se limpia luego).
                pos["_job_id"] = _extract_job_id(card, job_url)
                positions.append(pos)
                jobs_found += 1

        print(f"[LinkedIn] {jobs_found} posiciones en página {page_num + 1}")

        # El endpoint guest devuelve una cantidad variable por página (a veces
        # <25 aunque haya más). Solo cortamos cuando una página no aporta nada.
        if jobs_found == 0:
            break

        if page_num < max_pages - 1:
            random_delay(3000, 6000)

    print(f"[LinkedIn] Total: {len(positions)} posiciones encontradas")
    return positions


# ─── Orchestrator ─────────────────────────────────────────────

def scrape_source(source: str, keywords: str, config: dict) -> list:
    site_config = config.get("sites", {}).get(source, {})
    if not site_config.get("enabled", True):
        print(f"[{source}] Deshabilitado en config.")
        return []

    max_pages = site_config.get("max_pages", 3)

    if source == "linkedin":
        return scrape_linkedin(keywords, max_pages=max_pages)
    else:
        print(f"Fuente desconocida: {source}")
        return []


def scrape_all(keywords_list: list, sources: list, config: dict,
               region: str = None,
               linkedin_location: str = None,
               fetch_descriptions: bool = True,
               existing_desc_ids: set = None) -> dict:
    """Returns dict keyed by source with deduped positions."""
    results = {src: [] for src in sources}

    for keywords in keywords_list:
        for source in sources:
            if source == "linkedin":
                site_config = config.get("sites", {}).get(source, {})
                max_pages = site_config.get("max_pages", 3)
                new_positions = scrape_linkedin(
                    keywords,
                    max_pages=max_pages,
                    linkedin_location=linkedin_location
                )
            else:
                new_positions = scrape_source(source, keywords, config)
            results[source].extend(new_positions)
            random_delay(1000, 2000)

    # Dedup per source
    region = normalize_region(region if region is not None else target_region())
    for source in sources:
        before_geo = len(results[source])
        if region not in ("worldwide", ""):
            results[source] = filter_by_region(results[source], region)
            print(f"[{source}] {len(results[source])}/{before_geo} compatibles con {region} remoto")
        before_dedup = len(results[source])
        results[source] = dedup(results[source])
        print(f"[{source}] {before_dedup} -> {len(results[source])} despues de dedup")

    # 2ª pasada: descripciones de LinkedIn, solo sobre las vacantes conservadas.
    if fetch_descriptions and results.get("linkedin"):
        print(f"[LinkedIn] Enriqueciendo {len(results['linkedin'])} vacantes con su descripción...")
        results["linkedin"] = enrich_linkedin_descriptions(
            results["linkedin"], existing_desc_ids=existing_desc_ids
        )
    else:
        # Sin enriquecer: igual limpiamos el campo interno de todas las fuentes.
        for src_positions in results.values():
            for pos in src_positions:
                pos.pop("_job_id", None)

    return results


def _force_utf8():
    """Emite UTF-8 aunque la consola de Windows esté en cp1252, para que las
    descripciones/emojis no rompan el print del sample con UnicodeEncodeError."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def main():
    _force_utf8()
    parser = argparse.ArgumentParser(description="Scrape jobs from LinkedIn (guest endpoint)")
    parser.add_argument(
        "--source",
        default="linkedin",
        choices=["linkedin", "all"],
        help="Fuente a scrapear (default: linkedin)"
    )
    parser.add_argument("--keywords", required=True, help="Keywords (separadas por coma para múltiples búsquedas)")
    parser.add_argument(
        "--region", "--market",
        dest="region",
        default=None,
        choices=REGION_CHOICES,
        help="Filtro de elegibilidad geográfica. Default: TARGET_REGION del .env "
             "(y 'worldwide' si no está seteada). `--market` es un alias histórico."
    )
    parser.add_argument(
        "--linkedin-location",
        default=None,
        help="Ubicación enviada a LinkedIn (un NOMBRE de geografía, no un código "
             "de país). Default: LINKEDIN_LOCATION del .env ('Worldwide')."
    )
    parser.add_argument(
        "--skip-descriptions",
        action="store_true",
        help="No traer la descripción de cada vacante de LinkedIn (1 request extra "
             "por vacante). Por defecto SÍ se traen."
    )
    parser.add_argument("--save", action="store_true", help="Guarda resultados en .tmp/scraped_jobs.json")
    parser.add_argument("--add-to-sheets", action="store_true", help="Agrega resultados a Google Sheets")
    parser.add_argument("--search-name", default="default", help="Nombre de la búsqueda")
    args = parser.parse_args()

    config = load_config()
    keywords_list = [k.strip() for k in args.keywords.split(",") if k.strip()]

    # LinkedIn es la única fuente scrapeada; Wellfound y Fiverr fueron retirados.
    sources = ["linkedin"]

    # ① dedup-vs-Sheets: si vamos a guardar, leemos qué vacantes ya tienen
    # descripción en el tracker para no volver a pedirla (ahorra requests → 429).
    existing_desc_ids = set()
    if args.add_to_sheets and not args.skip_descriptions:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        try:
            from tools.sheets_manager import get_position_ids_with_description
            existing_desc_ids = get_position_ids_with_description()
            print(f"[dedup] {len(existing_desc_ids)} vacantes ya tienen descripción en Sheets; no se re-piden.")
        except Exception as e:
            print(f"[dedup] No se pudo leer Sheets ({e}); sigo sin dedup-vs-Sheets.")

    results = scrape_all(
        keywords_list,
        sources,
        config,
        region=args.region,
        linkedin_location=args.linkedin_location,
        fetch_descriptions=not args.skip_descriptions,
        existing_desc_ids=existing_desc_ids
    )

    all_positions = []
    for src_positions in results.values():
        all_positions.extend(src_positions)

    total_unique = len(dedup(all_positions))
    print(f"\nTotal: {len(all_positions)} posiciones ({total_unique} únicas cross-source)")

    if args.save:
        output_path = Path(".tmp/scraped_jobs.json")
        output_path.parent.mkdir(exist_ok=True)
        output_path.write_text(json.dumps(all_positions, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Guardado en {output_path}")

    if args.add_to_sheets:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from tools.sheets_manager import add_positions_bulk
        for pos in all_positions:
            pos["search_name"] = args.search_name
        result = add_positions_bulk(all_positions)
        print(f"\n{result['added']} posiciones agregadas a Google Sheets.")

    if not args.save and not args.add_to_sheets:
        sample = all_positions[:5]
        print(json.dumps(sample, ensure_ascii=False, indent=2))
        print(f"... ({len(all_positions)} total). Usá --save o --add-to-sheets para persistir.")


if __name__ == "__main__":
    main()
