"""
fetch_jobs_api.py — Obtiene posiciones de APIs públicas gratuitas (sin auth):
Remotive, Remote OK, Himalayas, Arbeitnow y Jobicy.
Uso: python core/fetch_jobs_api.py --keywords "automation engineer" --save

ATRIBUCIÓN / ToS: los feeds de Jobicy y Himalayas piden mencionar la fuente,
mantener el link a la vacante original (se conserva en el campo `url`) y NO
redistribuir a plataformas de terceros (LinkedIn, Google Jobs, Jooble, etc.).
Uso privado en el tracker del usuario → OK. No exportar estas filas a esas plataformas.
"""

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from env_config import target_region  # importing this loads data/credentials/.env
from location_filters import REGION_CHOICES, filter_by_region, normalize_region

REMOTIVE_URL = "https://remotive.com/api/remote-jobs"
REMOTEOK_URL = "https://remoteok.com/api"
HIMALAYAS_URL = "https://himalayas.app/jobs/api"
ARBEITNOW_URL = "https://www.arbeitnow.com/api/job-board-api"
JOBICY_URL = "https://jobicy.com/api/v2/remote-jobs"

# Fuentes disponibles (para --apis). Orden = orden de ejecución.
ALL_SOURCES = ["remotive", "remoteok", "himalayas", "arbeitnow", "jobicy"]

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; JobSearchBot/1.0)"}


def normalize_position(raw: dict, source: str) -> dict:
    return {
        "source": source,
        "tipo": "full-time",
        "company": raw.get("company", raw.get("company_name", "")),
        "role": raw.get("title", raw.get("position", "")),
        "url": raw.get("url", ""),
        "location": raw.get("candidate_required_location", raw.get("location", "Remote")),
        "remote": True,
        "salary": raw.get("salary", ""),
        "description": raw.get("description", "")[:3000],
        "tags": raw.get("tags", []),
        "date_posted": raw.get("publication_date", raw.get("date", "")),
    }


# Categorías de Remotive relevantes al perfil (segundo eje de discovery).
# NOTA: la API pública de Remotive está detrás de un cache de Cloudflare cuya
# clave ignora el query string, así que los parámetros `search`/`category` NO
# filtran del lado del servidor (todo request devuelve el mismo feed reciente).
# Por eso traemos el feed una sola vez y filtramos LOCALMENTE: por keyword
# (título/tags) y por el campo `category` que cada job ya trae. Los slugs de
# abajo se mapean al nombre visible con REMOTIVE_CATEGORY_NAMES.
DEFAULT_REMOTIVE_CATEGORIES = [
    "artificial-intelligence",
    "operations",
    "product",
    "software-development",
    "project-management",
]

# slug (endpoint /categories) → nombre visible que aparece en cada job.category
REMOTIVE_CATEGORY_NAMES = {
    "artificial-intelligence": "Artificial Intelligence",
    "operations": "Operations",
    "product": "Product Management",
    "software-development": "Software Development",
    "project-management": "Project Management",
    "data": "Data and Analytics",
    "devops": "Devops",
    "information-technology": "Information Technology",
    "business-development": "Business Development",
    "customer-service": "Customer Service",
    "all-others": "All others",
}


def _kw_match(title: str, tags: list, keywords_list: list) -> bool:
    """True si el título o los tags contienen alguna keyword (match multi-token AND)."""
    haystack = f"{title} {' '.join(tags or [])}".lower()
    for kw in keywords_list:
        tokens = [t for t in kw.lower().split() if t]
        if tokens and all(t in haystack for t in tokens):
            return True
    return False


def fetch_remotive(keywords_list: list, categories_list: list = None) -> list:
    """Trae el feed de Remotive una sola vez y filtra localmente.

    Se conserva un job si: (a) su título/tags matchea alguna keyword, o
    (b) su categoría está entre las categorías objetivo (segundo eje).
    """
    cats = categories_list or []
    target_names = {REMOTIVE_CATEGORY_NAMES.get(c, c).lower() for c in cats}
    print(f"[Remotive] Feed + filtro local | keywords={', '.join(keywords_list)} | categorías={', '.join(cats) or '-'}")
    try:
        resp = requests.get(
            REMOTIVE_URL,
            params={"limit": 100},
            headers=HEADERS,
            timeout=15
        )
        resp.raise_for_status()
        jobs = resp.json().get("jobs", [])
        matched = []
        for j in jobs:
            by_kw = _kw_match(j.get("title", ""), j.get("tags", []), keywords_list)
            by_cat = j.get("category", "").lower() in target_names
            if by_kw or by_cat:
                matched.append(j)
        print(f"[Remotive] {len(matched)}/{len(jobs)} tras filtro (keyword o categoria)")
        return [normalize_position(j, "remotive") for j in matched]
    except Exception as e:
        print(f"[Remotive] Error: {e}")
        return []


def _matches_keywords(job: dict, keywords_list: list) -> bool:
    """True si el título o los tags del job contienen alguna keyword.

    Solo se usa título + tags (no la descripción): tokens comunes como
    "operations" o "python" aparecen en casi cualquier descripción y bajan
    la precisión. Cada keyword multi-palabra hace match si TODOS sus tokens
    aparecen (ej. "automation engineer" matchea "Senior Automation Engineer").
    """
    haystack = " ".join([
        str(job.get("position", "")),
        " ".join(job.get("tags", []) or []),
    ]).lower()
    for kw in keywords_list:
        tokens = [t for t in kw.lower().split() if t]
        if tokens and all(t in haystack for t in tokens):
            return True
    return False


def fetch_remoteok(keywords_list: list) -> list:
    """Trae el feed completo de Remote OK una sola vez y filtra localmente.

    El parámetro `?tags=` de Remote OK espera tags atómicos (python, devops),
    no frases con espacios, así que filtramos del lado del cliente por título,
    tags y descripción contra todas las keywords de la sesión.
    """
    print(f"[Remote OK] Buscando (filtro local): {', '.join(keywords_list)}")
    try:
        resp = requests.get(REMOTEOK_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list) and data and "legal" in data[0]:
            data = data[1:]
        jobs = [j for j in data if isinstance(j, dict) and j.get("position")]
        matched = [j for j in jobs if _matches_keywords(j, keywords_list)]
        print(f"[Remote OK] {len(matched)}/{len(jobs)} resultados tras filtro por keywords")
        return [normalize_position(j, "remoteok") for j in matched]
    except Exception as e:
        print(f"[Remote OK] Error: {e}")
        return []


def _fmt_salary(smin, smax, currency="", period="") -> str:
    if not smin and not smax:
        return ""
    rng = "-".join(str(x) for x in (smin, smax) if x)
    return " ".join(p for p in (rng, str(currency or ""), str(period or "")) if p).strip()


# ─── Himalayas ────────────────────────────────────────────────
# Feed paginado (20/página vía offset). No filtra server-side (search/category
# se ignoran), así que traemos N páginas y filtramos localmente por keyword
# contra título + categories. Todas las vacantes son remotas por naturaleza.

def fetch_himalayas(keywords_list: list, max_pages: int = 5) -> list:
    print(f"[Himalayas] Feed + filtro local ({max_pages} págs) | keywords={', '.join(keywords_list)}")
    matched, scanned = [], 0
    try:
        for page in range(max_pages):
            resp = requests.get(
                HIMALAYAS_URL,
                params={"limit": 20, "offset": page * 20},
                headers=HEADERS, timeout=20
            )
            resp.raise_for_status()
            jobs = resp.json().get("jobs", [])
            if not jobs:
                break
            scanned += len(jobs)
            for j in jobs:
                cats = [str(c).replace("-", " ") for c in (j.get("categories") or [])]
                if _kw_match(j.get("title", ""), cats, keywords_list):
                    matched.append({
                        "source": "himalayas",
                        "tipo": "full-time",
                        "company": j.get("companyName", ""),
                        "role": j.get("title", ""),
                        "url": j.get("guid") or j.get("applicationLink", ""),
                        "location": ", ".join(j.get("locationRestrictions") or []) or "Remote",
                        "remote": True,
                        "salary": _fmt_salary(j.get("minSalary"), j.get("maxSalary"),
                                              j.get("currency"), j.get("salaryPeriod")),
                        "description": (j.get("description") or "")[:3000],
                        "tags": j.get("categories") or [],
                        "date_posted": j.get("pubDate", ""),
                    })
            time.sleep(0.5)
        print(f"[Himalayas] {len(matched)}/{scanned} tras filtro por keywords")
    except Exception as e:
        print(f"[Himalayas] Error: {e}")
    return matched


# ─── Arbeitnow ────────────────────────────────────────────────
# Feed paginado (100/página vía page). Foco EU/DACH con muchos NO remotos, así
# que filtramos por remote==True + keyword (título + tags) localmente.

def fetch_arbeitnow(keywords_list: list, max_pages: int = 3) -> list:
    print(f"[Arbeitnow] Feed + filtro local ({max_pages} págs) | keywords={', '.join(keywords_list)}")
    matched, scanned = [], 0
    try:
        for page in range(1, max_pages + 1):
            resp = requests.get(ARBEITNOW_URL, params={"page": page}, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            jobs = resp.json().get("data", [])
            if not jobs:
                break
            scanned += len(jobs)
            for j in jobs:
                if not j.get("remote"):
                    continue
                if _kw_match(j.get("title", ""), j.get("tags", []), keywords_list):
                    matched.append({
                        "source": "arbeitnow",
                        "tipo": "full-time",
                        "company": j.get("company_name", ""),
                        "role": j.get("title", ""),
                        "url": j.get("url", ""),
                        "location": j.get("location", "") or "Remote",
                        "remote": True,
                        "salary": "",
                        "description": (j.get("description") or "")[:3000],
                        "tags": j.get("tags") or [],
                        "date_posted": str(j.get("created_at", "")),
                    })
            time.sleep(0.5)
        print(f"[Arbeitnow] {len(matched)}/{scanned} tras filtro (remote + keyword)")
    except Exception as e:
        print(f"[Arbeitnow] Error: {e}")
    return matched


# ─── Jobicy ───────────────────────────────────────────────────
# Único de los tres con filtro server-side real: `tag` busca en título +
# descripción. Consultamos una vez por keyword (count=50) y dedupimos.

def fetch_jobicy(keywords_list: list, geo: str = "") -> list:
    print(f"[Jobicy] tag server-side | keywords={', '.join(keywords_list)}" + (f" | geo={geo}" if geo else ""))
    out, seen = [], set()
    for kw in keywords_list:
        params = {"count": 50, "tag": kw}
        if geo:
            params["geo"] = geo
        try:
            resp = requests.get(JOBICY_URL, params=params, headers=HEADERS, timeout=20)
            if resp.status_code == 404:
                print(f"[Jobicy] Sin resultados para '{kw}'" + (f" en geo={geo}" if geo else ""))
                continue
            resp.raise_for_status()
            jobs = resp.json().get("jobs", [])
            for j in jobs:
                jid = j.get("id") or j.get("url")
                if jid in seen:
                    continue
                seen.add(jid)
                out.append({
                    "source": "jobicy",
                    "tipo": (j.get("jobType") or ["full-time"])[0] if isinstance(j.get("jobType"), list) else (j.get("jobType") or "full-time"),
                    "company": j.get("companyName", ""),
                    "role": j.get("jobTitle", ""),
                    "url": j.get("url", ""),
                    "location": j.get("jobGeo", "") or "Remote",
                    "remote": True,
                    "salary": _fmt_salary(j.get("salaryMin"), j.get("salaryMax"),
                                          j.get("salaryCurrency"), j.get("salaryPeriod")),
                    "description": (j.get("jobDescription") or j.get("jobExcerpt") or "")[:3000],
                    "tags": j.get("jobIndustry") or [],
                    "date_posted": j.get("pubDate", ""),
                })
            time.sleep(0.5)
        except Exception as e:
            print(f"[Jobicy] Error con '{kw}': {e}")
            continue
    print(f"[Jobicy] {len(out)} resultados (deduplicados entre keywords)")
    return out


def dedup(positions: list) -> list:
    seen = set()
    unique = []
    for p in positions:
        key = f"{p['company'].lower().strip()}-{p['role'].lower().strip()}"
        key = "".join(c for c in key if c.isalnum() or c == "-")
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def fetch_all(keywords_list: list, categories_list: list = None,
              sources: list = None, jobicy_geo: str = "",
              region: str = None) -> list:
    sources = sources or ALL_SOURCES

    # Las 5 APIs son hosts independientes e I/O-bound: se disparan en paralelo,
    # así el tiempo total pasa de la SUMA de las 5 a la más lenta. Cada fetcher
    # ya captura sus propios errores y devuelve [], así que un fallo no frena al
    # resto. (Feed una-sola-vez + filtro local se conserva dentro de cada uno.)
    tasks = {}
    if "remotive" in sources:
        tasks["remotive"] = lambda: fetch_remotive(keywords_list, categories_list)
    if "remoteok" in sources:
        tasks["remoteok"] = lambda: fetch_remoteok(keywords_list)
    if "himalayas" in sources:
        tasks["himalayas"] = lambda: fetch_himalayas(keywords_list)
    if "arbeitnow" in sources:
        tasks["arbeitnow"] = lambda: fetch_arbeitnow(keywords_list)
    if "jobicy" in sources:
        tasks["jobicy"] = lambda: fetch_jobicy(keywords_list, geo=jobicy_geo)

    all_positions = []
    if tasks:
        with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
            futures = {executor.submit(fn): name for name, fn in tasks.items()}
            for future in as_completed(futures):
                name = futures[future]
                try:
                    all_positions.extend(future.result())
                except Exception as e:
                    print(f"[{name}] Error inesperado: {e}")

    region = normalize_region(region if region is not None else target_region())
    if region not in ("worldwide", ""):
        before_geo = len(all_positions)
        all_positions = filter_by_region(all_positions, region)
        print(f"[Geo] {len(all_positions)}/{before_geo} compatibles con {region} remoto")

    deduped = dedup(all_positions)
    print(f"\nTotal único: {len(deduped)} posiciones ({len(all_positions)} antes de dedup)")
    return deduped


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
    parser = argparse.ArgumentParser(description="Fetch jobs from Remotive and Remote OK APIs")
    parser.add_argument("--keywords", required=True, help="Keywords de búsqueda (separadas por coma para múltiples)")
    parser.add_argument(
        "--categories",
        default=",".join(DEFAULT_REMOTIVE_CATEGORIES),
        help="Categorías de Remotive como segundo eje (separadas por coma). "
             "Pasá '' para desactivar. Default: perfil objetivo configurado."
    )
    parser.add_argument(
        "--apis",
        default=",".join(ALL_SOURCES),
        help=f"Fuentes a consultar, separadas por coma. Opciones: {', '.join(ALL_SOURCES)}. Default: todas."
    )
    parser.add_argument(
        "--jobicy-geo",
        default="",
        help="Filtro geo opcional para Jobicy (ej. usa, latam, europe). Default: sin filtro."
    )
    parser.add_argument(
        "--region", "--market",
        dest="region",
        default=None,
        choices=REGION_CHOICES,
        help="Filtro de elegibilidad geográfica. Default: TARGET_REGION del .env "
             "(y 'worldwide' si no está seteada). `--market` es un alias histórico."
    )
    parser.add_argument("--save", action="store_true", help="Guarda resultados en .tmp/api_jobs.json")
    parser.add_argument("--add-to-sheets", action="store_true", help="Agrega resultados a Google Sheets")
    parser.add_argument("--search-name", default="default", help="Nombre de la búsqueda para el tracker")
    args = parser.parse_args()

    keywords_list = [k.strip() for k in args.keywords.split(",") if k.strip()]
    categories_list = [c.strip() for c in args.categories.split(",") if c.strip()]
    sources = [s.strip() for s in args.apis.split(",") if s.strip()]
    unknown = [s for s in sources if s not in ALL_SOURCES]
    if unknown:
        parser.error(f"Fuentes desconocidas en --apis: {unknown}. Válidas: {ALL_SOURCES}")
    positions = fetch_all(
        keywords_list,
        categories_list,
        sources=sources,
        jobicy_geo=args.jobicy_geo,
        region=args.region
    )

    if args.save:
        output_path = Path(".tmp/api_jobs.json")
        output_path.parent.mkdir(exist_ok=True)
        output_path.write_text(json.dumps(positions, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Guardado en {output_path}")

    if args.add_to_sheets:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from tools.sheets_manager import add_positions_bulk
        for pos in positions:
            pos["search_name"] = args.search_name
        result = add_positions_bulk(positions)
        print(f"\n{result['added']} posiciones agregadas a Google Sheets.")

    if not args.save and not args.add_to_sheets:
        print(json.dumps(positions[:5], ensure_ascii=False, indent=2))
        print(f"... ({len(positions)} total). Usá --save o --add-to-sheets para persistir.")


if __name__ == "__main__":
    main()
