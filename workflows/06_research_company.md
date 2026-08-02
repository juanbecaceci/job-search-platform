# Workflow 06 — Research a Company

## Objective
Build a structured intelligence brief on a target company before applying or
interviewing. The research powers CV personalization, cover-letter tone, and
interview preparation.

## When to Use
- Before generating application documents (Workflow 05, Step 1)
- Before an interview (Workflow 07)
- When the user wants to judge whether a company is worth applying to

---

## Inputs

| Input | Required |
|---|---|
| Company name | Yes — it's the dedupe key, and it's never editable |
| Company website URL | Yes |
| Industry / size | No |
| Target role title | Optional, but it unlocks the Indeed salary band |

---

## Execution

`POST /companies/{id}/research` → `202`. The `research_company` job scrapes
deterministically, then the agent synthesizes the brief and writes it to
`company.research_md` — a direct work-product write, no approval gate
(DECISIONS #14).

### Paso 1 — Scrapeo determinístico

`core/research_company.py` baja el texto público: homepage, About, Careers,
Blog, Google News. Es scraping plano, sin LLM.

### Paso 1b — Reviews y compensación (Indeed MCP, opcional)

```
mcp__claude_ai_Indeed__get_company_data
  companyName: "<company_name>"
  jobTitle: "<role_title>"
  location: { country: "<company_hq_country_iso2>", usState: null, usStateCode: null, usCity: null }
  knowledgeCategories: { metadata: true, ratings: true, salaries: true }
```

- `jobTitle` es el rol que el usuario está evaluando (habilita la banda salarial).
- `country` es el país de la sede/oferta de la empresa, **no** el del usuario ni
  `JOB_SEARCH_COUNTRY` — usar donde Indeed probablemente tiene más cobertura de
  esa empresa (ej. `US` para una empresa con sede en EE.UU.).
- Trae reviews verificadas de empleados, ratings (cultura, management,
  work-life balance) y salario promedio por rol — datos que el scraper del Paso
  1 no consigue.
- Requiere el conector de Indeed autorizado. Si no está, o si la empresa no
  tiene cobertura, **omitir la sección 5 del brief y seguir**. No es bloqueante.

### Paso 2 — Síntesis

El agente lee el texto scrapeado + la respuesta de Indeed y redacta el brief
estructurado (secciones abajo). Corre por la suscripción del usuario, no por API.

**Regla de oro: separar lo verificado de lo inferido.** Un brief que presenta
una suposición como hecho es peor que uno corto. Si la ronda de financiación no
aparece en ninguna fuente, decilo — no lo estimes.

---

## Secciones del brief

1. **Descripción General** — qué hacen, mercado, producto principal
2. **Modelo de Negocio** — B2B/B2C, modelo de ingresos, clientes clave
3. **Stack Tecnológico** — tecnologías encontradas públicamente
4. **Cultura y Valores** — estilo de trabajo, política de remoto, valores declarados
5. **Reviews y Compensación (Indeed)** — ratings de empleados, banda salarial
   para el rol objetivo. Omitir si no hay cobertura.
6. **Desafíos Conocidos** — desafíos, pivots, foco actual según noticias
7. **Por Qué Encaja el Perfil** — puntos de conexión concretos con el perfil
8. **Preguntas Estratégicas** — preguntas buenas para la entrevista
9. **Fuentes Consultadas** — URLs scrapeadas + Indeed (si aportó)

---

## Using the research

**CV (Workflow 05):** informa el Professional Summary y la selección de bullets.

**Cover letter (Workflow 05):** es de dónde sale la referencia específica a la
empresa. Una cover letter que cita un desafío real de la sección 6 se lee
distinto a una que parafrasea la homepage.

**Entrevista (Workflow 07):** las secciones 7 y 8 alimentan directamente la prep.

---

## Edge cases

**Scraping bloqueado (403 / captcha).** Algunas empresas bloquean scrapers.
Entonces: que el usuario pegue en el chat el texto de su LinkedIn, y sintetizá
desde ahí; Crunchbase o AngelList sirven para funding/tamaño.

**Sin sitio web (startup en stealth).** Buscar en LinkedIn, Crunchbase o
TechCrunch y pegar los hallazgos en el chat.

**Sin datos de Indeed.** Común en startups chicas o muy nuevas. Omitir la
sección 5 y seguir normal.

**Ya existe research.** Si `company.research_md` tiene contenido, reutilizalo en
vez de volver a scrapear — cuesta una vuelta de agente. Re-correr el job lo
sobrescribe, que es lo que se quiere para refrescarlo.

**El nombre de la empresa está mal escrito.** `name` es la clave de dedup y
**no** es editable por cambio propuesto. Si está mal, es un problema de datos a
resolver por otro lado, no algo que se arregle acá.

---

## Output

- `company.research_md` — el brief estructurado completo
- `industry`, `size`, `website` completados si el research los descubrió
