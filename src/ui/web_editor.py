from __future__ import annotations

import cgi
import json
import mimetypes
import socket
from datetime import datetime
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Callable
from uuid import uuid4

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QHBoxLayout, QTextEdit, QWidget

from core.settings import settings

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
except Exception:  # pragma: no cover
    QWebEngineView = None


class _EditorServer:
    def __init__(self) -> None:
        self.runtime_dir = settings.data_dir / "web_editor_runtime"
        self.assets_dir = self.runtime_dir / "assets" / "mublo-editor"
        self.upload_dir = self.runtime_dir / "uploads"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self._copy_assets()
        self._write_index_html()

        self.port = self._find_free_port()
        handler_cls = partial(_EditorRequestHandler, directory=str(self.runtime_dir), upload_dir=self.upload_dir)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", self.port), handler_cls)
        self.thread = Thread(target=self.httpd.serve_forever, daemon=True)

    def start(self) -> None:
        if not self.thread.is_alive():
            self.thread.start()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @staticmethod
    def _find_free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return int(s.getsockname()[1])

    def _copy_assets(self) -> None:
        source_dir = settings.project_root / "src" / "blogwriter" / "ui" / "assets" / "mublo-editor"
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        for name in ["MubloEditor.js", "MubloEditor.css"]:
            src = source_dir / name
            dst = self.assets_dir / name
            if src.exists():
                dst.write_bytes(src.read_bytes())

    def _write_index_html(self) -> None:
        html = """<!DOCTYPE html>
<html lang=\"ko\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>MubloOps Editor</title>
  <link href=\"/assets/mublo-editor/MubloEditor.css\" rel=\"stylesheet\" />
  <style>
    html, body { height: 100%; margin: 0; background: #fff; }
    .wrap { height: 100%; }
    .mublo-editor { height: 100%; }
  </style>
</head>
<body>
  <div class=\"wrap\">
    <textarea id=\"editor\" class=\"mublo-editor\"></textarea>
  </div>

  <script src=\"/assets/mublo-editor/MubloEditor.js\"></script>
  <script>
    window.__editor = null;

    function ensureEditor() {
      if (window.__editor) return window.__editor;
      window.__editor = MubloEditor.create('#editor', {
        toolbar: 'full',
        height: '100%',
        uploadUrl: '/upload',
        showWordCount: true,
        placeholder: '내용을 입력하세요...'
      });
      return window.__editor;
    }

    window.setEditorHtml = function (html) {
      const ed = ensureEditor();
      ed.setHTML(html || '');
    }

    window.getEditorHtml = function () {
      const ed = ensureEditor();
      return ed.getHTML();
    }

    ensureEditor();
  </script>
</body>
</html>
"""
        (self.runtime_dir / "index.html").write_text(html, encoding="utf-8")


class _EditorRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory: str, upload_dir: Path, **kwargs):
        self.upload_dir = upload_dir
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def do_POST(self) -> None:  # noqa: N802
        if self.path.split("?")[0] != "/upload":
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        ctype, _ = cgi.parse_header(self.headers.get("Content-Type", ""))
        if ctype != "multipart/form-data":
            self._write_json({"error": "Invalid content type"}, status=HTTPStatus.BAD_REQUEST)
            return

        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": self.headers.get("Content-Type", ""),
                "CONTENT_LENGTH": self.headers.get("Content-Length", "0"),
            },
        )

        if "file" not in form:
            self._write_json({"error": "file field is required"}, status=HTTPStatus.BAD_REQUEST)
            return

        item = form["file"]
        if isinstance(item, list):
            item = item[0]

        original_name = Path(item.filename or "image").name
        suffix = Path(original_name).suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
            self._write_json({"error": "Unsupported image type"}, status=HTTPStatus.BAD_REQUEST)
            return

        data = item.file.read()
        if not data:
            self._write_json({"error": "Empty file"}, status=HTTPStatus.BAD_REQUEST)
            return
        if len(data) > 8 * 1024 * 1024:
            self._write_json({"error": "File too large (max 8MB)"}, status=HTTPStatus.BAD_REQUEST)
            return

        filename = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}{suffix}"
        save_path = self.upload_dir / filename
        save_path.write_bytes(data)

        mime = mimetypes.guess_type(save_path.name)[0] or "application/octet-stream"
        self._write_json(
            {
                "url": f"/uploads/{filename}",
                "filename": filename,
                "originalName": original_name,
                "size": len(data),
                "type": mime,
            }
        )

    def _write_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


_SERVER: _EditorServer | None = None


def get_editor_server() -> _EditorServer:
    global _SERVER
    if _SERVER is None:
        _SERVER = _EditorServer()
        _SERVER.start()
    return _SERVER


class MubloWebEditor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._ready = False
        self._pending_html: str | None = None

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        if QWebEngineView is None:
            self._fallback = QTextEdit()
            layout.addWidget(self._fallback)
            self.setLayout(layout)
            return

        self._fallback = None
        self._view = QWebEngineView()
        self._view.loadFinished.connect(self._on_loaded)
        server = get_editor_server()
        self._view.setUrl(QUrl(f"{server.base_url}/index.html"))
        layout.addWidget(self._view)
        self.setLayout(layout)

    def _on_loaded(self, ok: bool) -> None:
        self._ready = bool(ok)
        if self._ready and self._pending_html is not None:
            self.set_html(self._pending_html)
            self._pending_html = None

    def set_html(self, html: str) -> None:
        if self._fallback is not None:
            self._fallback.setHtml(html or "")
            return
        if not self._ready:
            self._pending_html = html or ""
            return
        payload = json.dumps(html or "", ensure_ascii=False)
        self._view.page().runJavaScript(f"window.setEditorHtml({payload});")

    def get_html(self, callback: Callable[[str], None]) -> None:
        if self._fallback is not None:
            callback(self._fallback.toHtml())
            return
        if not self._ready:
            callback("")
            return
        self._view.page().runJavaScript("window.getEditorHtml();", callback)

