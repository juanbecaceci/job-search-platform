# Workflow 05 — Generate Application Documents

## Objective
For a `Shortlisted` position: research the company, generate a tailored ATS-optimized CV (PDF + DOCX), generate a personalized cover letter (PDF + DOCX), upload both to Google Drive, and update the position status to `Ready to Apply`.

## When to Use
After the user marks a position as `Shortlisted` in Workflow 04.

---

## Inputs

| Input | Source |
|---|---|
| position_id | Google Sheets |
| Job description | Sheets → `description` field |
| Candidate profile | `context/professional_profile.md` |
| Company research | Generated in Step 1 below |
| Tone preference | the user's choice: formal / startup / consulting |

---

## Steps

> **Nota de arquitectura:** la redacción (CV, cover letter, research) la hago yo (Claude Code)
> en la conversación usando tu suscripción. Los tools solo hacen el trabajo determinístico:
> scraping, export a PDF/DOCX y guardado. No se consume Anthropic API.

### Step 1: Research the Company

Always do this before generating the CV. Research personalizes both the summary and cover letter.
Ver **Workflow 06** para el detalle. Resumen: `--scrape` baja el texto, yo sintetizo, `--save` guarda.

Output: `output/companies/<company>/research.md`

### Step 2: Generate the CV

1. **Yo redacto el CV** en Markdown leyendo `context/professional_profile.md` + el JD (del campo
   `notes` de la posición) + el research. Aplico las reglas del perfil (caso insignia como logro
   principal, niveles de skills tal como fueron declarados, keywords del JD para ATS, sin métricas inventadas).
2. Lo guardo en `output/cvs/<position_id>/cv.md`.
3. Exporto a PDF + DOCX (determinístico):
   ```bash
   python core/generate_cv.py --export --position-id <position_id>
   ```
   Genera: `output/cvs/<position_id>/cv.pdf` y `cv.docx`.

**Validation checklist before proceeding:**
- [ ] Flagship case is the lead achievement with its validated metrics
- [ ] Skill levels match the profile's declared levels (no inflation)
- [ ] No invented metrics
- [ ] Summary is tailored to this specific role/company
- [ ] Keywords from the JD appear naturally in the CV
- [ ] No tables or multi-column layout (ATS-safe)

### Step 3: Edit the CV (if needed)

The user pide cambios por chat. **Yo reescribo el `cv.md`** y vuelvo a exportar:
```bash
python core/generate_cv.py --export --position-id <position_id>
```

Example edits:
- "Agrega mención de SQL en la sección de skills técnicos"
- "El summary es muy genérico, enfocalo más en el dominio del rol"
- "Borrá el bullet de docencia, no es relevante para este rol"

Repeat until the user is satisfied.

### Step 4: Generate the Cover Letter

1. **Yo redacto la cover letter** (≤350 palabras) leyendo perfil + JD + research, con el tono
   apropiado a la empresa, y la guardo en `output/cover_letters/<position_id>/cover_letter.md`.
2. Exporto a PDF + DOCX:
   ```bash
   python core/generate_cover_letter.py --export --position-id <position_id>
   ```

**Guía de tono (la aplico al redactar):**
- **formal**: banks, large corporations, traditional enterprise
- **startup**: seed to Series B startups, product companies
- **consulting**: consulting firms, agencies, professional services

**Validation:**
- [ ] Under 350 words
- [ ] Opens with the flagship achievement (or the most relevant one for this role)
- [ ] References the company specifically (not generic)
- [ ] No clichés ("I believe I am a perfect fit")
- [ ] Clear call to action

Para editar: reescribo el `cover_letter.md` y vuelvo a correr `--export`.

### Step 5: Upload to Google Drive

Use the Google Drive MCP to upload:
```
mcp__claude_ai_Google_Drive__create_file
```

Upload:
- `output/cvs/<position_id>/cv.pdf`
- `output/cvs/<position_id>/cv.docx`
- `output/cover_letters/<position_id>/cover_letter.pdf`

Save the Drive URLs.

### Step 6: Update Sheets

```bash
python core/sheets_manager.py --action update_status --id <position_id> --status "Ready to Apply"
```

Also log the Drive URL in the `notes` field.

---

## Output

- `output/cvs/<position_id>/cv.pdf` + `cv.docx`
- `output/cover_letters/<position_id>/cover_letter.pdf` + `cover_letter.docx`
- Google Drive: both files uploaded
- Sheets: status → `Ready to Apply`, Drive URLs recorded

---

## Next Step

→ Apply to the position and run:
```bash
python core/sheets_manager.py --action log_application --id <position_id>
```
Status → `Applied`

→ After applying: set up Gmail monitoring (Workflow 02 → Gmail section)

→ If interview scheduled: **Workflow 07 — Interview Prep**
