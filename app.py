import os
from flask import Flask, request, jsonify, send_file, render_template, Response
from werkzeug.utils import secure_filename
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from io import BytesIO

from converter import convert_to_pdf, extract_from_zip
from database import init_db, get_pix_key, get_total_conversions, increment_conversions

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)

ALLOWED_EXTENSIONS = {".zpl", ".txt", ".zip"}
ZPL_SIGNATURES = (b"^XA", b"^xa", b"^Xa")
ZIP_MAGIC = b"PK\x03\x04"


def _ext(filename: str) -> str:
    return os.path.splitext(filename)[1].lower()


def _validate_file(filename: str, data: bytes) -> str | None:
    """Return error string or None if valid."""
    ext = _ext(filename)
    if ext not in ALLOWED_EXTENSIONS:
        return f"Tipo não permitido: '{ext}'. Use .zpl, .txt ou .zip"
    if ext == ".zip":
        if not data.startswith(ZIP_MAGIC):
            return "Arquivo ZIP inválido (magic bytes incorretos)"
    else:
        stripped = data.lstrip()
        if not any(stripped.startswith(sig) for sig in ZPL_SIGNATURES):
            return "Arquivo ZPL inválido (deve começar com ^XA)"
    return None


@app.after_request
def set_security_headers(resp: Response) -> Response:
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "script-src 'self' 'unsafe-inline' https://pagead2.googlesyndication.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self'; "
        "frame-src https://googleads.g.doubleclick.net https://tpc.googlesyndication.com;"
    )
    return resp


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/stats")
def stats():
    return jsonify({
        "total_conversions": get_total_conversions(),
        "pix_key": get_pix_key(),
    })


@app.route("/api/convert", methods=["POST"])
@limiter.limit("10 per minute")
def convert():
    uploads = request.files.getlist("file")
    uploads = [u for u in uploads if u.filename]
    if not uploads:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    all_files = []
    try:
        for upload in uploads:
            filename = secure_filename(upload.filename)
            data = upload.read()

            if not data:
                return jsonify({"error": f"Arquivo vazio: {filename}"}), 400

            error = _validate_file(filename, data)
            if error:
                return jsonify({"error": error}), 400

            ext = _ext(filename)
            if ext == ".zip":
                extracted = extract_from_zip(data)
                if not extracted:
                    return jsonify({"error": f"Nenhum .txt encontrado em: {filename}"}), 400
                all_files.extend(extracted)
            else:
                all_files.append((filename, data))

        if not all_files:
            return jsonify({"error": "Nenhum arquivo ZPL válido encontrado"}), 400

        pdf_bytes = convert_to_pdf(all_files)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        app.logger.error("Erro na conversão: %s", e)
        return jsonify({"error": "Falha na conversão. Tente novamente."}), 500

    increment_conversions()

    return send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name="etiquetas.pdf",
    )


@app.errorhandler(413)
def too_large(_):
    return jsonify({"error": "Arquivo muito grande. Limite: 10 MB"}), 413


@app.errorhandler(429)
def rate_limit_exceeded(_):
    return jsonify({"error": "Muitas requisições. Aguarde 1 minuto."}), 429


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
