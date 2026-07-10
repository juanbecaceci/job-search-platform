"""
parse_profile.py — Extrae texto crudo de un documento de perfil (PDF / DOCX / TXT).

El razonamiento (estructurar el perfil en Markdown) lo hace Claude Code en la conversación,
usando los tokens de tu suscripción — NO consume Anthropic API tokens.

Flujo:
1. Ejecutá este tool para extraer el texto crudo del documento.
2. Pasame el texto (o el archivo de salida) en la conversación.
3. Yo estructuro y escribo context/professional_profile.md siguiendo las reglas del proyecto.

Uso: python core/parse_profile.py --input context/raw/mi_perfil.pdf
     python core/parse_profile.py --input context/raw/mi_perfil.pdf --output .tmp/raw_profile.txt
"""

import argparse
import sys
from pathlib import Path


def extract_text_from_pdf(pdf_path: Path) -> str:
    try:
        import pypdf
    except ImportError:
        print("pypdf no instalado. Instalá con: pip install pypdf")
        sys.exit(1)
    reader = pypdf.PdfReader(str(pdf_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def extract_text_from_docx(docx_path: Path) -> str:
    try:
        from docx import Document
    except ImportError:
        print("python-docx no instalado. Instalá con: pip install python-docx")
        sys.exit(1)
    doc = Document(str(docx_path))
    return "\n".join(para.text for para in doc.paragraphs)


def extract_text(input_path: Path) -> str:
    ext = input_path.suffix.lower()
    if ext == ".pdf":
        return extract_text_from_pdf(input_path)
    elif ext in (".docx", ".doc"):
        return extract_text_from_docx(input_path)
    elif ext == ".txt":
        return input_path.read_text(encoding="utf-8")
    else:
        print(f"Formato no soportado: {ext}. Usá PDF, DOCX o TXT.")
        sys.exit(1)


def main():
    # En Windows la consola usa cp1252 por defecto y falla al imprimir caracteres
    # como "→" o acentos. Forzamos UTF-8 en stdout para evitar UnicodeEncodeError.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    parser = argparse.ArgumentParser(
        description="Extrae texto crudo de un documento de perfil (PDF/DOCX/TXT)."
    )
    parser.add_argument("--input", required=True, help="Ruta al documento fuente")
    parser.add_argument("--output", help="Ruta de salida del texto (default: stdout)")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: archivo no encontrado: {input_path}")
        sys.exit(1)

    raw_text = extract_text(input_path)

    if not raw_text.strip():
        print("Error: no se pudo extraer texto (¿PDF escaneado? probá exportar a TXT).")
        sys.exit(1)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(raw_text, encoding="utf-8")
        print(f"Texto extraído ({len(raw_text)} caracteres) → {output_path}")
        print("Ahora pasame este archivo en la conversación y estructuro el perfil.")
    else:
        sys.stdout.write(raw_text)


if __name__ == "__main__":
    main()
