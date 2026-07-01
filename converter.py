import glob
import os
import re
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO

import requests
from PIL import Image

# 2 colunas de 4cm x 5cm = 80mm x 50mm = 3.15" x 1.97"
LABEL_SIZE = "3.15x1.97"
LABELARY_BASE = "http://api.labelary.com/v1/printers/8dpmm/labels/{size}/0/"
HEADERS = {"Accept": "image/png"}
MAX_WORKERS = 4


def split_zpl_blocks(zpl_text: str) -> list[str]:
    blocks = re.findall(r'\^[Xx][Aa].*?\^[Xx][Zz]', zpl_text, re.DOTALL)
    return blocks if blocks else [zpl_text]


def _fetch_image(block: str, size: str = LABEL_SIZE, max_retries: int = 6) -> Image.Image:
    url = LABELARY_BASE.format(size=size)
    for attempt in range(max_retries):
        try:
            resp = requests.post(url, data=block.encode("utf-8"), headers=HEADERS, timeout=30)
            if resp.status_code == 429:
                wait = 2 ** (attempt + 1)
                print(f"  rate limit, aguardando {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return Image.open(BytesIO(resp.content)).convert("RGB")
        except requests.exceptions.Timeout:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)
    resp.raise_for_status()


def extract_from_zip(zip_bytes: bytes) -> list[tuple[str, bytes]]:
    results = []
    with zipfile.ZipFile(BytesIO(zip_bytes), "r") as zf:
        names = sorted(zf.namelist())
        for name in names:
            if ".." in name or name.startswith("/") or name.startswith("\\") or os.path.isabs(name):
                raise ValueError(f"ZIP entry com caminho suspeito bloqueado: {name!r}")
            basename = os.path.basename(name).lower()
            if basename.endswith(".txt"):
                results.append((basename, zf.read(name)))
    return results


def convert_to_pdf(files: list[tuple[str, bytes]], label_size: str = LABEL_SIZE) -> bytes:
    ordered: list[tuple[int, str]] = []
    for name, content in files:
        zpl_text = content.decode("utf-8", errors="replace")
        blocks = split_zpl_blocks(zpl_text)
        print(f"  {name}: {len(blocks)} bloco(s)")
        for block in blocks:
            ordered.append((len(ordered), block))

    total = len(ordered)
    print(f"  Total: {total} etiqueta(s) — {MAX_WORKERS} workers paralelos\n")

    results: dict[int, Image.Image] = {}
    errors: list[str] = []

    def fetch_indexed(idx_block: tuple[int, str]) -> tuple[int, Image.Image]:
        idx, block = idx_block
        return idx, _fetch_image(block, label_size)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(fetch_indexed, item): item[0] for item in ordered}
        done = 0
        for future in as_completed(futures):
            done += 1
            idx = futures[future]
            try:
                resolved_idx, img = future.result()
                results[resolved_idx] = img
                print(f"  [{done}/{total}] etiqueta {resolved_idx + 1} OK")
            except Exception as exc:
                msg = f"etiqueta {idx + 1}: {exc}"
                errors.append(msg)
                print(f"  [{done}/{total}] ERRO — {msg}")

    if errors:
        raise RuntimeError(f"Falha em {len(errors)} etiqueta(s):\n" + "\n".join(errors))

    images = [results[i] for i in range(total)]

    buf = BytesIO()
    images[0].save(buf, format="PDF", save_all=True, append_images=images[1:], resolution=203.0)
    return buf.getvalue()


# --- CLI ---

def _load_file(path: str) -> tuple[str, bytes]:
    with open(path, "rb") as f:
        return (os.path.basename(path), f.read())


def main():
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
            glob.glob(os.path.join(folder, "*.txt")) +
            glob.glob(os.path.join(folder, "*.zpl"))
        )
        files = [_load_file(p) for p in paths]

    if not files:
        print("Nenhum arquivo ZPL (.txt/.zpl) encontrado.")
        sys.exit(1)

    print(f"{len(files)} arquivo(s) encontrado(s).\n")
    pdf_bytes = convert_to_pdf(files)

    output = os.path.join(folder, "etiquetas.pdf")
    with open(output, "wb") as f:
        f.write(pdf_bytes)
    print(f"\nPDF gerado: {output}  ({len(pdf_bytes) // 1024} KB)")


if __name__ == "__main__":
    main()
