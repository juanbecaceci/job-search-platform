# Workflow 01 — Build / Update Professional Profile

## Objective
Maintain `context/professional_profile.md` as the authoritative source of truth for the user's professional data. This file feeds every other workflow in the system.

## When to Use
- First time setup (profile doesn't exist yet)
- New document with updated experience, certifications, or skills
- the user provides corrections or additions in conversation

---

## Inputs

| Input | Source | Required |
|---|---|---|
| Source document | PDF, DOCX, or TXT in `context/raw/` | For document-based update |
| Conversation notes | the user's verbal corrections/additions | For conversational update |

---

## Steps

### A. Document-Based Update

1. Confirm the source document is in `context/raw/`
2. Extract the raw text (determinístico, sin API):
   ```
   py core/parse_profile.py --input context/raw/<filename> --output .tmp/raw_profile.txt
   ```
   > **Nota (Windows):** en esta máquina Python se invoca con `py` (el launcher),
   > **no** con `python`/`python3` — esos son alias del Microsoft Store que fallan.
   > Python instalado: 3.14.x. Si el archivo tiene espacios en el nombre, poné la
   > ruta entre comillas (ej: `"context/raw/Profile LinkedIn.pdf"`).
3. Pasame el archivo `.tmp/raw_profile.txt` en la conversación. **Yo (Claude Code) estructuro
   el perfil** y escribo `context/professional_profile.md` siguiendo las reglas del proyecto —
   esto usa los tokens de tu suscripción, no la API.
4. Output: `context/professional_profile.md` (overwrites previous version)
5. **Validate** — check these sections are correct before proceeding:
   - Datos Personales: name, email, location, salary target
   - Logros Cuantificables: the flagship case's validated metrics are present, verbatim (never rounded up or embellished)
   - Skills Técnicos: skill levels match exactly what the user declared — never inflate them
   - Reglas para Generación de CV: all content rules defined by the user must be present

### B. Conversational Update

1. The user provides corrections or new information in chat
2. Read current `context/professional_profile.md`
3. Apply changes manually using the Edit tool
4. Examples:
   - New certification: add to "Certificaciones y Premios"
   - New job: add to "Experiencia Laboral" with STAR bullets + metrics
   - Updated salary target: update "Pretensión salarial" + scoring criteria

---

## Validation Checklist

Before marking the profile as complete, verify:

- [ ] Flagship case includes all of its validated metrics, verbatim
- [ ] Awards and certifications are listed in Certificaciones
- [ ] Skill levels match the user's declared levels (no inflation)
- [ ] All CV generation content rules are present
- [ ] Keywords ATS section is in English
- [ ] Professional Summary is in English
- [ ] Salary target matches the user's configured salary floor

---

## Edge Cases

**Empty PDF output:** pypdf sometimes fails on scanned PDFs. Fallback: use Adobe Acrobat to export as TXT, then run with `--input context/raw/file.txt`

**`python` no encontrado (Windows):** usar `py` en lugar de `python`/`python3`. Los alias `python.exe`/`python3.exe` en `WindowsApps` son stubs del Microsoft Store y devuelven exit 49. `parse_profile.py` ya fuerza UTF-8 en stdout, así que el `print` final no rompe en consolas cp1252.

**Outdated profile:** If more than 3 months old, prompt the user to confirm all data is still accurate before running a job search.

---

## Output

- `context/professional_profile.md` — updated and validated
