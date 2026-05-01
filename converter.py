import glob
import os
import sys
import time
import zipfile
from io import BytesIO

import requests
from PIL import Image

LABELARY_URL = "http://api.labelary.com/v1/printers/8dpmm/labels/4x6/0/"
HEADERS = {"Accept": "image/png"}


def zpl_to_image(zpl_content: str) -> Image.Image:
    for attempt in range(5):
        resp = requests.post(LABELARY_URL, data=zpl_content.encode("utf-8"), headers=HEADERS)
        if resp.status_code == 429:
            wait = 2 * (attempt + 1)
            print(f"  rate limit, aguardando {wait}s...")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return Image.open(BytesIO(resp.content)).convert("RGB")
    resp.raise_for_status()


def extract_from_zip(zip_bytes: bytes) -> list[tuple[str, bytes]]:
    """Extract .txt ZPL files from ZIP bytes. Raises ValueError on ZIP slip attempt."""
    results = []
    with zipfile.ZipFile(BytesIO(zip_bytes), "r") as zf:
        names = sorted(zf.namelist())
        for name in names:
            # ZIP slip prevention
            if ".." in name or name.startswith("/") or name.startswith("\\") or os.path.isabs(name):
                raise ValueError(f"ZIP entry com caminho suspeito bloqueado: {name!r}")
            basename = os.path.basename(name).lower()
            if basename.endswith(".txt"):
                results.append((basename, zf.read(name)))
    return results


def convert_to_pdf(files: list[tuple[str, bytes]]) -> bytes:
    """Convert list of (filename, zpl_bytes) to a multi-page PDF. Returns PDF bytes."""
    images = []
    total = len(files)
    for i, (name, content) in enumerate(files, 1):
        print(f"  [{i}/{total}] {name}")
        zpl_text = content.decode("utf-8", errors="replace")
        images.append(zpl_to_image(zpl_text))
        if i < total:
            time.sleep(1.0)

    buf = BytesIO()
    images[0].save(buf, format="PDF", save_all=True, append_images=images[1:], resolution=203.0)
    return buf.getvalue()


# --- CLI (backward compat) ---

def _load_file(path: str) -> tuple[str, bytes]:
    with open(path, "rb") as f:
        return (os.path.basename(path), f.read())


def main():
    import tempfile

    folder = sys.argv[1] if len(sys.argv) > 1 else "."
    folder = os.path.abspath(folder)

    zip_paths = sorted(glob.glob(os.path.join(folder, "*.zip")))
    if zip_paths:
        print(f"{len(zip_paths)} ZIP(s) encontrado(s). Extraindo...")
        files = []
        for zip_path in zip_paths:
            with open(zip_path, "rb") as f:
                files.extend(extract_from_zip(f.read()))
    else:
        paths = sorted(
            glob.glob(os.path.join(folder, "*label*.txt")) +
            glob.glob(os.path.join(folder, "*.zpl"))
        )
        files = [_load_file(p) for p in paths]

    if not files:
        print("Nenhum arquivo ZPL encontrado.")
        sys.exit(1)

    print(f"{len(files)} etiqueta(s) encontrada(s).\n")
    pdf_bytes = convert_to_pdf(files)

    output = os.path.join(folder, "etiquetas.pdf")
    with open(output, "wb") as f:
        f.write(pdf_bytes)
    print(f"\nPDF gerado: {output}  ({len(files)} etiquetas)")


if __name__ == "__main__":
    main()
