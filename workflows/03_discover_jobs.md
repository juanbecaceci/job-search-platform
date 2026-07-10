# Workflow 03 — Discover Jobs

## Objective
Pull job listings from all configured sources, deduplicate, and store them in Google Sheets with status `Discovered`. Feed the scoring pipeline in Workflow 04.

## When to Use
After completing Workflow 02 (search configured).

---

## Inputs

| Input | Where |
|---|---|
| Search name | From Workflow 02 |
| Keywords list | From Workflow 02 / `config/job_sites.json` |
| Sources to activate | From Workflow 02 |

---

## Execution Sequence

### Step 1: APIs (fastest, no rate limits)

```bash
python core/fetch_jobs_api.py \
  --keywords "automation engineer,AI operations,product operations,workflow automation" \
  --categories "artificial-intelligence,operations,product,software-development,project-management" \
  --market latam-argentina \
  --jobicy-geo latam \
  --save \
  --add-to-sheets \
  --search-name <search_name>
```

- **Cinco APIs públicas sin auth:** **Remotive**, **Remote OK**, **Himalayas**, **Arbeitnow**, **Jobicy**.
- Seleccioná un subconjunto con `--apis "jobicy,himalayas"` (default: todas). Fuente que más aporta hoy: **Jobicy** (único con filtro server-side real).
- Saves to `.tmp/api_jobs.json`. Adds deduped positions to Sheets with status `Discovered`.
- **Ejecución en paralelo:** las 5 APIs son hosts independientes e I/O-bound, así
  que se disparan **concurrentemente** (`ThreadPoolExecutor`). El tiempo total es
  el de la fuente más lenta, no la suma de las 5 (~7 s medido, antes ~1 min). Cada
  fetcher mantiene su patrón feed-una-vez + filtro local y captura sus propios
  errores, así que si una API falla, el resto sigue. No hay riesgo de 429 acá
  (hosts distintos, pocos requests por fuente).
- **Carga a Sheets:** los tools usan inserción bulk para evitar el límite de
  lecturas por minuto de Google Sheets. Si una corrida vieja falla con HTTP 429
  de Sheets, los resultados locales ya guardados en `.tmp/api_jobs.json` o
  `.tmp/scraped_jobs.json` se pueden reintentar con el mismo comando.
- **Filtro geográfico default:** `--market latam-argentina` conserva solo roles
  remotos compatibles con Argentina/LATAM o remoto global (`Worldwide`,
  `Anywhere`, `Global`). Descarta posiciones bloqueadas a US/UK/Europe/Canada
  cuando no indiquen LATAM/global.

**Mecánica de filtrado por fuente** (todas devuelven un feed; el filtro varía):

| Fuente | Filtrado | Notas |
|---|---|---|
| **Jobicy** | **Server-side** vía `tag` (busca título + descripción) | 1 request por keyword, `count` máx 50. Geo default: `--jobicy-geo latam` (otros: `usa`, `canada`, `europe`). Lo mejor de los 5. |
| **Remotive** | Local — 1 request, filtra por keyword (título/tags) **∪** categoría | Server-side roto: cache de Cloudflare ignora el query string (`search`/`category` no filtran). 2 ejes vía `--keywords` y `--categories`. |
| **Remote OK** | Local — 1 request al feed, filtra por keyword (título/tags) | `?tags=` espera tags atómicos, no frases. |
| **Himalayas** | Local — pagina 5×20 vía offset, filtra por keyword (título/categories) | `search` se ignora server-side. Todo remoto. |
| **Arbeitnow** | Local — pagina 3×100 vía page, filtra por `remote==True` + keyword | Foco EU/DACH: muchos NO remotos se descartan. |

**Dos ejes de discovery en Remotive:** `--keywords` (match título/tags) y `--categories` (conserva jobs de esas categorías aunque el título no matchee). Slugs en `https://remotive.com/api/remote-jobs/categories`. Default = perfil objetivo configurado; `--categories ""` desactiva el eje.

> **ToS / atribución.** Jobicy y Himalayas exigen mencionar la fuente, conservar el link a la vacante original (siempre se guarda en `url`) y **NO redistribuir a plataformas de terceros** (LinkedIn, Google Jobs, Jooble). El tracker del usuario es de uso privado → OK. **No exportar estas filas a esas plataformas.** Arbeitnow/Remotive/Remote OK: uso libre con link de vuelta.

### Step 2: Indeed (official MCP connector)

Primary method in Claude (this environment has the connector; Codex does not —
see fallback below):

```
mcp__claude_ai_Indeed__search_jobs
  search: "<keyword>"
  location: "remote"
  country_code: "AR"
```

- Correr una vez por keyword del set activo (mismas keywords que el resto del
  discovery, ver `search_keywords_by_role` en `config/job_sites.json`).
- El resultado viene en **markdown** (títulos + link de apply), no JSON
  estructurado. El agente arma, para cada listado conservado, un registro con
  el mismo shape que usa el resto de las fuentes: `source="indeed"`, `tipo`,
  `company`, `role`, `url` (el link de apply — **no recortar parámetros**),
  `location`, `remote`, `salary` (si aparece), `description` (vacío si el
  listado no la trae — pedir `get_job_details(job_id)` solo si hace falta más
  detalle puntual, no para las 50 vacantes de entrada), `tags`, `date_posted`.
- Aplicar el mismo criterio geográfico Argentina/LATAM/remoto global que
  `core/location_filters.py` al leer los resultados (descartar roles
  bloqueados a US/UK/Europe/Canada sin mención LATAM/global).
- Guardar el array armado en `.tmp/indeed_jobs.json` y cargarlo con:

```bash
py core/load_positions_bulk.py \
  --file .tmp/indeed_jobs.json \
  --market latam-argentina \
  --search-name <search_name>
```

- `core/load_positions_bulk.py` hace el dedup (mismo key company+role+url) y
  el insert bulk a Sheets — no cargar fila por fila con `add_position` para no
  pisar el límite de rate de Sheets.
- `mcp__claude_ai_Indeed__get_company_data` (reviews/ratings/salarios reales
  de empleados) queda disponible para Workflow 06 — más rico que el research
  actual, usarlo ahí en vez de en discovery.

**Fallback — Scrappa Indeed Jobs API** (solo si el conector no está disponible
en el entorno, p. ej. Codex, donde el OAuth del MCP oficial completa pero
sesiones nuevas fallan con `HTTP 403 invalid_client` porque el MCP es beta
Claude-Connector-only):

```bash
py core/fetch_jobs_indeed.py \
  --keywords "automation engineer,AI operations,product operations,workflow automation" \
  --location Argentina \
  --country ar \
  --market latam-argentina \
  --save \
  --add-to-sheets \
  --search-name <search_name>
```

Requiere `SCRAPPA_API_KEY` en `.env`. No correr repetidamente sin aprobación de
The user si los créditos son pagos. No scrapear el HTML de Indeed directamente.

### Step 3: LinkedIn scraper (guest endpoint)

```bash
python core/scrape_jobs.py \
  --source linkedin \
  --keywords "automation engineer,automation consultant,AI consultant,product operations,workflow automation,solutions engineer,deployment strategist,forward-deployed builder,applied AI engineer,AI agent engineer,conversational AI" \
  --market latam-argentina \
  --linkedin-location Argentina \
  --save \
  --add-to-sheets \
  --search-name <search_name>
```

- **LinkedIn es la única fuente scrapeada.** Wellfound y Fiverr fueron retirados (ver nota abajo y Step 4b).
- Usa el endpoint público **`jobs-guest`** (`/jobs-guest/jobs/api/seeMoreJobPostings/search`): devuelve el HTML de las tarjetas sin login ni Playwright. Rápido y liviano (`requests` + BS4).
- Pagina de a 25 con `start`. `max_pages` en [config/job_sites.json](../config/job_sites.json) (default 3).
- **No sacar un eje de keywords por completo al afinar la búsqueda.** El matching de `jobs-guest` es literal por frase, no semántico: si una corrida elimina un grupo de keywords entero para reducir ruido, también deja de traer vacantes reales que usan esas frases en el título. **Mantené los ejes configurados en paralelo** (ver `config/job_sites.json` → `search_keywords_by_role`). El ruido de roles no alineados se filtra mejor en Workflow 04 vía `profile_alignment`, no recortando ejes en el discovery.
- **Cubrir variantes de título del mismo rol (p. ej. "consultant" además de "engineer").** Muchos roles equivalentes usan títulos distintos ("AI Consultant" vs "AI Engineer", "specialist" vs "analyst"). Incluir las variantes relevantes en cada eje para no perder vacantes que matchean el perfil pero titulan diferente.
- **Patrón recurrente: startups AI-native usan títulos no estándar** ("Deployment Strategist", "Forward-Deployed Builder", "Applied AI Engineer") que no matchean keywords convencionales. Estrategia: parchear keyword por keyword cuando se detecta un miss (más simple, menos ruido). Si los misses se vuelven frecuentes, considerar una query amplia (p. ej. `--keywords "AI"`) con filtrado local posterior. Ante señales de riesgo en una vacante (empresa sin trayectoria verificable, salario atípicamente alto, estructuras de pago inusuales), cargarla igual con una nota de precaución en `notes` para no perder la señal, marcando due diligence pendiente antes de aplicar.

**Descripciones (2ª pasada):** las tarjetas de la búsqueda **no** traen la
descripción. Por eso, tras paginar, filtrar por geografía y deduplicar, el tool
hace una **segunda pasada** que pide la descripción de cada vacante conservada
al endpoint de detalle `/jobs-guest/jobs/api/jobPosting/<job_id>` (selector
`.show-more-less-html__markup`). Se persiste en la columna `description` de
Sheets (truncada a 3000 chars).

- Es **1 request extra por vacante** → aumenta el riesgo de 429. Por eso corre
  **solo sobre las vacantes que sobreviven** al filtro geo + dedup, no sobre todo
  lo scrapeado, y espacia cada pedido 1.2–2.8 s.
- Desactivable con **`--skip-descriptions`** (más rápido, sin descripción de
  LinkedIn) si solo querés el barrido de metadata o venís rate-limiteado.

**Cuatro palancas anti-429** (activas por defecto):

1. **Dedup contra Sheets** — antes de enriquecer, el tool lee del tracker qué
   vacantes **ya tienen descripción** (`get_position_ids_with_description`) y
   **no las vuelve a pedir**. Re-correr un search prácticamente no gasta requests
   de detalle. Requiere `--add-to-sheets` (si no, no hay tracker que consultar).
2. **Cache local por `job_id`** — `.tmp/li_desc_cache.json`. Una descripción ya
   traída no se vuelve a pedir, aunque la vacante aparezca bajo otra keyword o en
   otra corrida/día. El archivo vive en `.tmp/` (disposable, gitignored).
3. **Priming de cookies** — antes de paginar y antes de enriquecer, el tool hace
   un GET a la página real de búsqueda para setear las cookies de invitado
   (`bcookie`, `lidc`); las llamadas guest con esas cookies tienen un techo de
   rate más alto.
4. **Backoff adaptativo** — ante un 429, espera (respetando el header
   `Retry-After` si viene, si no backoff exponencial con jitter) y **reintenta
   hasta 2 veces**. Solo corta la 2ª pasada si el 429 **persiste** tras los
   reintentos; en ese caso **conserva todas las vacantes** con su metadata (las
   descripciones faltantes se completan en la próxima corrida vía cache + dedup).

El log final del enriquecimiento resume: `N nuevas, M de cache, K ya en Sheets`.

Notes:
- Se rate-limitea (**HTTP 429**) tras ~10 páginas por IP en la búsqueda; el
  enriquecimiento de descripciones suma requests y puede adelantar ese límite.
  Si pasa, el tool corta solo; esperá ~30 min y reintentá.
- Ya **no** requiere `playwright install`.

> **Wellfound / Fiverr retirados.** Wellfound puso DataDome + Cloudflare en toda ruta de búsqueda (403 sin proxy residencial + navegador anti-detect), y Fiverr publica gigs que ofrece el freelancer, no vacantes. Startups → carga manual (Step 4b). Freelance → Upwork MCP (Step 4).

### Step 4: Upwork MCP (freelance/contract)

```
mcp__claude_ai_Upwork__upwork_search_freelancers
```

Search for relevant project postings. Store with `tipo: freelance`.

### Step 4b: Carga manual (startups / vacantes sueltas)

Cuando el usuario suba vacantes al chat (p. ej. de Wellfound u otras fuentes que revise a mano), parsearlas y almacenarlas con `sheets_manager.add_position()` (status `Discovered`, `source: manual`). Entran al mismo pipeline de dedup y scoring que el resto.

---

## Deduplication Logic

The tool handles dedup automatically:
- Primary key: MD5 hash of `normalize(company) + normalize(role)`
- If a position already exists: source is added to the `sources[]` field, no new row created
- Cross-source positions are unified

---

## After Discovery

Check the count in Sheets:
```
python core/sheets_manager.py --action get_by_status --status Discovered
```

Expected: ~30-80 positions for a broad keyword search (Remotive + Remote OK feeds están acotados a decenas cada uno; LinkedIn e Indeed suman el grueso).

If count is very low (<20):
- Broaden keywords y/o categorías (`--categories`).
- Chequeá si LinkedIn se rate-limiteó (HTTP 429) — esperá ~30 min.
- Los feeds de Remotive/Remote OK rotan (~feed reciente); si están "flacos" ese día, apoyate en Indeed vía `core/fetch_jobs_indeed.py` y LinkedIn.
- Try Indeed provider with broader terms.

---

## Output

- Google Sheets → "Positions" sheet: rows with `status = Discovered`.
  El esquema incluye las columnas **`description`** y **`tags`**: la descripción
  de la vacante ahora se persiste (APIs + Indeed la traen del feed; LinkedIn vía
  la 2ª pasada del Step 3). Es el texto que consume la evaluación (Workflow 04) y
  el tailoring del CV (Workflow 05), no solo título/salario.
- `.tmp/api_jobs.json` and `.tmp/scraped_jobs.json` — local cache

---

## Next Step

→ Run **Workflow 04 — Evaluate & Rank**
