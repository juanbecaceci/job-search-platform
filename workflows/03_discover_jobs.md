# Workflow 03 — Discover Jobs

## Objective
Pull job listings from the configured sources, deduplicate them, and store them
as `positions` rows with status `Discovered`. Feeds the scoring pipeline in
Workflow 04.

## When to Use
After Workflow 02 (search configured).

---

## Two ways this runs — know which one you're in

**The platform (normal path).** `POST /searches/{id}/run` returns `202` with a
job id and streams per-source progress over SSE. The `search_run` job handler
imports the `core/` fetchers **in-process** and persists straight to SQLite. It
does **not** apply a geographic filter — positions are stored as the fetchers
matched them.

**The standalone CLIs (manual path).** The `core/*.py` commands below still work
for a one-off run outside the app. They *do* filter by region (`--region`,
default `TARGET_REGION`) and they write to Google Sheets, not to the app's
database. Use them for debugging a source, not as the normal flow.

Everything about *how each source behaves* applies to both.

---

## Inputs

| Input | Where |
|---|---|
| Search name / id | From Workflow 02 |
| Keywords list | From Workflow 02 / `config/job_sites.json` → `search_keywords_by_role` |
| Sources to activate | From Workflow 02 |

---

## The sources

### Step 1: The five free APIs (fastest, no auth, no rate limits)

Standalone equivalent:

```bash
python core/fetch_jobs_api.py \
  --keywords "<keyword,keyword,...>" \
  --categories "<slug,slug,...>" \
  --region "<o se omite: toma TARGET_REGION del .env>" \
  --save \
  --search-name <search_name>
```

- **Cinco APIs públicas sin auth:** **Remotive**, **Remote OK**, **Himalayas**, **Arbeitnow**, **Jobicy**.
- Seleccioná un subconjunto con `--apis "jobicy,himalayas"` (default: todas). Fuente que más aporta hoy: **Jobicy** (único con filtro server-side real).
- **Ejecución en paralelo:** las 5 APIs son hosts independientes e I/O-bound, así
  que se disparan **concurrentemente** (`ThreadPoolExecutor`). El tiempo total es
  el de la fuente más lenta, no la suma de las 5 (~7 s medido, antes ~1 min). Cada
  fetcher mantiene su patrón feed-una-vez + filtro local y captura sus propios
  errores, así que si una API falla, el resto sigue. No hay riesgo de 429 acá
  (hosts distintos, pocos requests por fuente).
- **Filtro geográfico (solo camino standalone):** `--region` (alias histórico:
  `--market`) toma por default `TARGET_REGION` del `.env`, y ese default es
  `worldwide` = **no filtra nada**. Con una región concreta (`latam`,
  `north-america`, `europe`, `apac`) conserva los roles compatibles con esa
  región más el remoto global (`Worldwide`, `Anywhere`, `Global`) y descarta los
  bloqueados a otra región. Las listas de términos están en
  `core/location_filters.py`.

**Mecánica de filtrado por fuente** (todas devuelven un feed; el filtro varía):

| Fuente | Filtrado | Notas |
|---|---|---|
| **Jobicy** | **Server-side** vía `tag` (busca título + descripción) | 1 request por keyword, `count` máx 50. `--jobicy-geo` es opcional y por default va vacío (sin filtro geo); valores: `usa`, `latam`, `canada`, `europe`. Lo mejor de los 5. |
| **Remotive** | Local — 1 request, filtra por keyword (título/tags) **∪** categoría | Server-side roto: cache de Cloudflare ignora el query string (`search`/`category` no filtran). 2 ejes vía `--keywords` y `--categories`. |
| **Remote OK** | Local — 1 request al feed, filtra por keyword (título/tags) | `?tags=` espera tags atómicos, no frases. |
| **Himalayas** | Local — pagina 5×20 vía offset, filtra por keyword (título/categories) | `search` se ignora server-side. Todo remoto. |
| **Arbeitnow** | Local — pagina 3×100 vía page, filtra por `remote==True` + keyword | Foco EU/DACH: muchos NO remotos se descartan. |

**Dos ejes de discovery en Remotive:** `--keywords` (match título/tags) y `--categories` (conserva jobs de esas categorías aunque el título no matchee). Slugs en `https://remotive.com/api/remote-jobs/categories`. `--categories ""` desactiva el eje.

> **ToS / atribución.** Jobicy y Himalayas exigen mencionar la fuente, conservar el link a la vacante original (siempre se guarda en `url`) y **NO redistribuir a plataformas de terceros** (LinkedIn, Google Jobs, Jooble). El tracker del usuario es de uso privado → OK. **No exportar estas filas a esas plataformas.** Arbeitnow/Remotive/Remote OK: uso libre con link de vuelta.

### Step 2: Indeed (MCP connector)

In the platform this is `api/agent/mcp_sources.py:fetch_indeed`, which lives in
`api/agent/` rather than `core/` because resolving a connector is an LLM call
(DECISIONS #27). It costs one agent turn per run.

```
mcp__claude_ai_Indeed__search_jobs
  search: "<keyword>"
  location: "<JOB_SEARCH_LOCATION del .env, default 'remote'>"
  country_code: "<JOB_SEARCH_COUNTRY del .env, default 'US'>"
```

- Correr una vez por keyword del set activo.
- El resultado viene en **markdown** (títulos + link de apply), no JSON
  estructurado. Se arma, para cada listado conservado, un registro con el mismo
  shape que el resto de las fuentes: `source="indeed"`, `tipo`, `company`,
  `role`, `url` (el link de apply — **no recortar parámetros**), `location`,
  `remote`, `salary` (si aparece), `description`, `tags`, `date_posted`.
- **Las descripciones se piden en la MISMA vuelta del agente.** Indeed reemite
  el `job_id` por sesión, así que un id guardado no se puede resolver en un job
  posterior (DECISIONS #30). Gobernado por `INDEED_FETCH_DESCRIPTIONS`
  (default on) y `INDEED_MAX_DETAILS` (default 25). Medido: 10 vacantes ~25 s
  sin descripciones, ~136 s con (~11 s cada una).
- **La URL de Indeed no es un permalink.** Cada llamada devuelve un token de
  redirect nuevo para la misma vacante, así que el dedup **nunca** va por URL:
  va por `company + role`, igual que `make_position_id`.
- Si el conector no está registrado, la fuente se marca **`skipped`**, no
  `error` (DECISIONS #27). No es un fallo a debuggear.
- `mcp__claude_ai_Indeed__get_company_data` (reviews/ratings/salarios reales de
  empleados) queda para Workflow 06, no para discovery.

**Fallback — Scrappa Indeed Jobs API** (si el conector no está disponible en el
entorno):

```bash
py core/fetch_jobs_indeed.py \
  --keywords "<keyword,keyword,...>" \
  --location "<o se omite: toma JOB_SEARCH_LOCATION del .env>" \
  --country "<o se omite: toma JOB_SEARCH_COUNTRY del .env>" \
  --region "<o se omite: toma TARGET_REGION del .env>" \
  --save \
  --search-name <search_name>
```

Requiere `SCRAPPA_API_KEY` en el `.env`. Es de pago: no correrlo repetidamente
sin que el usuario lo apruebe. No scrapear el HTML de Indeed directamente.

### Step 3: LinkedIn (public guest endpoint)

En la plataforma es `_fetch_linkedin` en `api/jobs/handlers/search_run.py` —
HTTP plano en proceso, **sin** vuelta del agente (a diferencia de `indeed`).
Standalone:

```bash
python core/scrape_jobs.py \
  --source linkedin \
  --keywords "<keyword,keyword,...>" \
  --region "<o se omite: toma TARGET_REGION del .env>" \
  --linkedin-location "<o se omite: toma LINKEDIN_LOCATION del .env, default 'Worldwide'>" \
  --save \
  --search-name <search_name>
```

- Usa el endpoint público **`jobs-guest`** (`/jobs-guest/jobs/api/seeMoreJobPostings/search`): devuelve el HTML de las tarjetas sin login ni Playwright. Rápido y liviano (`requests` + BS4). Ya **no** requiere `playwright install`.
- Pagina de a 25 con `start`. `LINKEDIN_MAX_PAGES` en el `.env` (default 3).
- `LINKEDIN_LOCATION` espera un **nombre** de geografía, no un código de país. `Worldwide` es un valor propio de LinkedIn y es el default.
- **No sacar un eje de keywords por completo al afinar la búsqueda.** El matching de `jobs-guest` es literal por frase, no semántico: si una corrida elimina un grupo de keywords entero para reducir ruido, también deja de traer vacantes reales que usan esas frases en el título. **Mantené los ejes en paralelo.** El ruido de roles no alineados se filtra mejor en Workflow 04 vía `profile_alignment`, no recortando ejes en el discovery.
- **Cubrir variantes de título del mismo rol** (p. ej. "consultant" además de "engineer"). Muchos roles equivalentes usan títulos distintos ("AI Consultant" vs "AI Engineer", "specialist" vs "analyst").
- **Patrón recurrente: las startups AI-native usan títulos no estándar** ("Deployment Strategist", "Forward-Deployed Builder", "Applied AI Engineer") que no matchean keywords convencionales. Estrategia: parchear keyword por keyword cuando se detecta un miss. Si los misses se vuelven frecuentes, considerar una query amplia (p. ej. `--keywords "AI"`) con filtrado local posterior. Ante señales de riesgo en una vacante (empresa sin trayectoria verificable, salario atípicamente alto, estructuras de pago inusuales), cargarla igual con una nota de precaución en `notes` para no perder la señal, marcando due diligence pendiente antes de aplicar.

**Descripciones (2ª pasada):** las tarjetas de la búsqueda **no** traen la
descripción. Tras paginar y deduplicar, se hace una **segunda pasada** que pide
la descripción de cada vacante conservada al endpoint de detalle
`/jobs-guest/jobs/api/jobPosting/<job_id>` (selector
`.show-more-less-html__markup`), truncada a 3000 chars. Se controla con
`LINKEDIN_FETCH_DESCRIPTIONS`.

- Es **1 request extra por vacante** → aumenta el riesgo de 429. Por eso corre
  **solo sobre las vacantes que sobreviven** al dedup, y espacia cada pedido.

**Tres palancas anti-429** (activas por defecto):

1. **Cache por `job_id`** — en `data/cache/` (gitignored). Una descripción ya
   traída no se vuelve a pedir, aunque la vacante aparezca bajo otra keyword o
   en otra corrida. Medido: 10 vacantes en 27 s en frío, 1 s en caliente.
   ⚠️ Este cache guarda texto de vacantes, o sea datos del usuario: vive bajo
   `data/`, nunca en `.tmp/` (DECISIONS #31).
2. **Priming de cookies** — antes de paginar y antes de enriquecer se hace un
   GET a la página real de búsqueda para setear las cookies de invitado
   (`bcookie`, `lidc`); las llamadas guest con esas cookies tienen un techo de
   rate más alto.
3. **Backoff adaptativo** — ante un 429 espera (respetando `Retry-After` si
   viene, si no backoff exponencial con jitter) y **reintenta hasta 2 veces**.
   Solo corta la 2ª pasada si el 429 **persiste**; en ese caso **conserva todas
   las vacantes** con su metadata y las descripciones faltantes se completan en
   la próxima corrida vía cache.

Notes:
- Se rate-limitea (**HTTP 429**) tras ~10 páginas por IP en la búsqueda; el
  enriquecimiento suma requests y puede adelantar ese límite. Si pasa, el tool
  corta solo; esperá ~30 min y reintentá.

### Step 4: Manual (startups / vacantes sueltas)

Cuando el usuario suba una vacante al chat, se carga con `POST /positions`
(`source: manual`, status `Discovered`). Entra al mismo pipeline de dedup y
scoring que el resto.

> **Wellfound y Fiverr no son fuentes.** Wellfound puso DataDome + Cloudflare en
> toda ruta de búsqueda (403 sin proxy residencial), y Fiverr publica gigs que
> ofrece el freelancer, no vacantes. Startups → carga manual.

---

## Deduplication

Automático, y es la misma clave en todo el sistema:

- **Clave: `make_position_id(company, role)`** — el slug normalizado de empresa
  + rol. **Nunca la URL**: Indeed rota su token de redirect y LinkedIn también
  varía sus links, así que dedupear por URL deja pasar duplicados.
- Si la posición ya existe: se le suma la fuente al campo `sources[]` y se
  vincula a esta corrida con `is_new=False` — no se crea fila nueva.
- Una posición nueva se inserta con status `Discovered` y `is_new=True`.
- El dedup corre contra **todo** lo ya almacenado, no solo contra esta corrida,
  así que re-correr una búsqueda trae lo nuevo en vez de duplicar.

---

## After discovery

En la app: la pantalla de detalle de la búsqueda muestra el total por fuente y
cuántas fueron nuevas; `GET /positions?status=Discovered` da lo mismo por API.

Esperable: ~30-80 posiciones para una búsqueda amplia (los feeds de Remotive y
Remote OK están acotados a decenas cada uno; LinkedIn e Indeed suman el grueso).

Si el número es muy bajo (<20):
- Ampliá keywords y/o categorías (`--categories`).
- Fijate si LinkedIn se rate-limiteó (HTTP 429) — esperá ~30 min.
- Fijate si `indeed` quedó **`skipped`** por conector sin autorizar.
- Los feeds de Remotive/Remote OK rotan; si están flacos ese día, apoyate en
  Indeed y LinkedIn.
- En el camino standalone, revisá `TARGET_REGION`: una región angosta descarta
  mucho, y una región no reconocida avisa una vez por stderr.

---

## Output

- `positions` rows con `status = Discovered`, vinculadas a un `search_runs` vía
  `search_run_positions`.
- La columna **`description`** es la que consumen la evaluación (Workflow 04) y
  el tailoring del CV (Workflow 05) — no solo título/salario. Por eso las
  descripciones están on por default en Indeed y LinkedIn pese a su costo.

---

## Next Step

→ **Workflow 04 — Evaluate & Rank**
