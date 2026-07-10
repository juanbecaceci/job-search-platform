# Workflow 06 — Research a Company

## Objective
Build a structured intelligence brief on a target company before applying or interviewing. The research powers CV personalization, cover letter tone, and interview preparation.

## When to Use
- Before generating application documents (Workflow 05, Step 1)
- Before an interview (Workflow 07)
- When the user wants to assess if a company is worth applying to

---

## Inputs

| Input | Required |
|---|---|
| Company name | Yes |
| Company website URL | Yes |
| Industry (optional) | No |
| Company size (optional) | No |

---

## Execution

Dos pasos: **el tool scrapea** (determinístico) y **yo (Claude Code) sintetizo** el brief.

### Paso 1 — Scrapear el texto crudo

```bash
python core/research_company.py --scrape \
  --company "<company_name>" \
  --url "<company_website>" \
  --output .tmp/<company>_raw.json
```

The tool scrapes: Homepage, About, Careers, Blog, Google News.

### Paso 1b — Reviews y compensación (Indeed MCP)

```
mcp__claude_ai_Indeed__get_company_data
  companyName: "<company_name>"
  jobTitle: "<role_title>"
  language: "es"
  location: { country: "<company_hq_country_iso2>", usState: null, usStateCode: null, usCity: null }
  knowledgeCategories: { metadata: true, ratings: true, salaries: true }
```

- `jobTitle` es el rol al que the user está evaluando/aplicando (habilita la banda salarial). `country`
  es el país de la sede/oferta de la empresa (no Argentina por default) — usar el país donde Indeed
  probablemente tiene más cobertura de esa empresa (ej. "US" para una empresa con sede en EE.UU.).
- Trae reviews verificadas de empleados, ratings (cultura, management, work-life balance, etc.) y
  salario promedio por rol — datos que el scraper del Paso 1 no consigue.
- **Empresas chicas / startups nuevas a veces no tienen datos en Indeed.** Si la respuesta viene vacía
  o sin cobertura, omitir la sección 5 del brief sin bloquear el resto del research.

### Paso 2 — Yo sintetizo el brief

Leo `.tmp/<company>_raw.json` + la respuesta del Paso 1b, redacto el research estructurado (secciones
abajo) en Markdown y lo guardo en `.tmp/<company>_research.md`. Esto usa tu suscripción, no la API.

### Paso 3 — Guardar + registrar en Sheets

```bash
python core/research_company.py --save \
  --company "<company_name>" \
  --url "<company_website>" \
  --md-file .tmp/<company>_research.md \
  --industry "<industry>" \
  --size "<size>" \
  --add-to-sheets
```

Guarda en `output/companies/<company>/research.md` y registra en la hoja "Companies".

---

## Output Report Sections

The synthesized report (`output/companies/<company>/research.md`) contains:

1. **Descripción General** — What they do, market, core product
2. **Modelo de Negocio** — B2B/B2C, revenue model, key customers
3. **Stack Tecnológico** — Technologies found publicly
4. **Cultura y Valores** — Work style, remote policy, stated values
5. **Reviews y Compensación (Indeed)** — Employee ratings (culture, management, work-life
   balance), salary band for the target role. Omitir si Indeed no tiene cobertura de la empresa.
6. **Desafíos Conocidos** — Challenges, pivots, focus areas from news
7. **Por Qué Encaja el Perfil** — Specific connection points to the user's profile
8. **Preguntas Estratégicas** — Smart questions for the interview
9. **Fuentes Consultadas** — URLs scraped + Indeed (si aportó datos)

---

## Using the Research

**For CV generation:** leo `output/companies/<company>/research.md` al redactar el CV — informa el
Professional Summary y la selección de bullets.

**For cover letter:** lo mismo al redactar la cover letter — para referenciar los desafíos/valores
específicos de la empresa.

**For interviews:** The "Por Qué Encaja el Perfil" and "Preguntas Estratégicas" sections feed directly into Workflow 07.

---

## Edge Cases

**Scraping blocked (403 / captcha):** Some companies block scrapers. In that case:
1. Visit the company's LinkedIn page manually and paste relevant text into chat
2. I'll synthesize from that content instead
3. Check Crunchbase or AngelList for funding/size info

**No website (startup in stealth):** Search for the company on LinkedIn, Crunchbase, or TechCrunch. Paste any findings into chat.

**Sin datos de Indeed (Paso 1b vacío):** común en startups chicas o muy nuevas. Omitir la sección
5 del brief y seguir con el resto del research normalmente — no es un bloqueante.

**Cached research exists:** si `output/companies/<company>/research.md` ya existe, reutilizalo en
vez de volver a scrapear. Para refrescar, corré `--scrape` de nuevo y re-sintetizá.

---

## Output

- `output/companies/<company>/research.md` — full structured brief
- Google Sheets → "Companies" sheet: company record with research path
