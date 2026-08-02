"""
upload_to_drive.py — Sube archivos LOCALES (PDF/DOCX/etc.) a una carpeta de Google
Drive vía la Drive API. DETERMINÍSTICO.

Por qué existe: el conector MCP de Drive exige incrustar el binario como base64
inline, lo que es inviable para PDFs (se trunca / no se puede pasar íntegro por la
interfaz de herramientas). Este tool lee el archivo del disco y lo sube directo con
`MediaFileUpload`, sin pasar el contenido por la conversación.

Auth: delegada a `core/google_auth.py` — un único token en `data/credentials/`
con scopes de Sheets + Drive. Autorizá una sola vez con
`python scripts/authorize_google.py`; desde el server se usa
`get_drive_service(interactive=False)`, que nunca abre el navegador.

Uso:
  py core/upload_to_drive.py --folder-id <ID> \
     --file "ruta/local.pdf::Nombre-Visible.pdf" \
     --file "ruta/otra.pdf::Otro-Nombre.pdf"
"""

import argparse
import mimetypes
import sys
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Run directly (`py core/upload_to_drive.py`) sys.path[0] is core/, so the
# `core.google_auth` import in `get_drive_service` would not resolve. Put the
# repo root on the path; imported as `core.upload_to_drive` this is a no-op.
_ROOT = str(Path(__file__).resolve().parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Scopes/paths live in core/google_auth.py now (one token, under data/).
# Kept as names for backwards compatibility with anything importing them.
SCOPES = ["https://www.googleapis.com/auth/drive"]


def _force_utf8():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def get_drive_service(interactive: bool = True):
    """Build the Drive client.

    Credentials now come from `core/google_auth.py` (token under
    `data/credentials/`, shared with Sheets) instead of a `token_drive.json` at
    the repo root — that path violated hard rule #1 and forced a second browser
    authorization. `interactive=False` is what job handlers pass so a server
    never blocks on an OAuth prompt.
    """
    from core.google_auth import get_credentials

    creds = get_credentials(interactive=interactive)
    return build("drive", "v3", credentials=creds)


def ensure_folder(service, name: str, parent_id: str) -> str:
    """Return the id of the `name` subfolder under `parent_id`, creating it if needed.

    Idempotent by name: re-uploading a document must land in the same folder as
    the first upload, not spawn a duplicate. Drive happily allows two folders
    with the same name in the same parent, so this looks before it creates.
    """
    safe = name.replace("\\", "\\\\").replace("'", "\\'")
    query = (
        f"name = '{safe}' and '{parent_id}' in parents "
        "and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    )
    found = service.files().list(q=query, fields="files(id)", pageSize=1).execute().get("files", [])
    if found:
        return found[0]["id"]

    created = service.files().create(
        body={
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        },
        fields="id",
    ).execute()
    return created["id"]


def upload_file(
    service, local_path: str, title: str, folder_id: str, replace_existing: bool = False
) -> dict:
    """Upload `local_path` into `folder_id` as `title`.

    With `replace_existing`, a file of the same name in that folder is updated
    in place instead of being duplicated. Re-exporting and re-uploading a
    document is routine (you tweak the CV and send it again), and without this
    the folder fills with identically-named copies — and the document's stored
    `drive_url` would point at whichever one happened to be uploaded last.
    Updating keeps the id, so previously-shared links stay valid.
    """
    path = Path(local_path)
    if not path.exists():
        print(f"[skip] No existe: {local_path}")
        return {}
    mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    fields = "id, name, size, md5Checksum, webViewLink"

    if replace_existing:
        safe = title.replace("\\", "\\\\").replace("'", "\\'")
        existing = service.files().list(
            q=f"name = '{safe}' and '{folder_id}' in parents and trashed = false",
            fields="files(id)",
            pageSize=1,
        ).execute().get("files", [])
        if existing:
            media = MediaFileUpload(str(path), mimetype=mime, resumable=False)
            updated = service.files().update(
                fileId=existing[0]["id"], media_body=media, fields=fields
            ).execute()
            print(f"[updated] {title}  ({updated.get('size','?')} bytes)")
            print(f"     {updated.get('webViewLink','')}")
            return updated

    media = MediaFileUpload(str(path), mimetype=mime, resumable=False)
    metadata = {"name": title, "parents": [folder_id]}
    created = service.files().create(
        body=metadata, media_body=media, fields=fields,
    ).execute()
    print(f"[ok] {title}  ({created.get('size','?')} bytes, md5 {created.get('md5Checksum','?')})")
    print(f"     {created.get('webViewLink','')}")
    return created


def main():
    _force_utf8()
    parser = argparse.ArgumentParser(description="Sube archivos locales a una carpeta de Google Drive")
    parser.add_argument("--folder-id", required=True, help="ID de la carpeta destino en Drive")
    parser.add_argument("--file", action="append", required=True,
                        help="Par 'ruta_local::Titulo-visible'. Repetible.")
    args = parser.parse_args()

    service = get_drive_service()
    results = []
    for item in args.file:
        if "::" in item:
            local_path, title = item.split("::", 1)
        else:
            local_path, title = item, Path(item).name
        results.append(upload_file(service, local_path.strip(), title.strip(), args.folder_id))

    ok = [r for r in results if r]
    print(f"\n{len(ok)}/{len(args.file)} archivos subidos a la carpeta {args.folder_id}.")


if __name__ == "__main__":
    main()
