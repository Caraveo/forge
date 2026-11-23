"""Private local asset bridge for Dimension's embedded renderer.

Dimension is a local Ubuntu application, not a remote service. Its renderer
expects its UI and a model's sidecar textures to share an HTTP origin; this
bridge gives the FORGE chat a token-scoped, loopback-only origin.
"""
from __future__ import annotations

import mimetypes
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

DIMENSION_UI = Path("/usr/lib/dimension/ui")

_FORGE_PAGE = """<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'self'; script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval'; img-src 'self' blob: data:; connect-src 'self' blob: data:; worker-src 'self' blob:; style-src 'self'\"><title>Dimension in FORGE</title><link rel=\"stylesheet\" href=\"style.css\"><script type=\"importmap\">{\"imports\":{\"three\":\"./vendor/build/three.module.js\",\"three/addons/\":\"./vendor/examples/jsm/\"}}</script></head><body><button id=\"open\" hidden>Open model</button><main id=\"stage\" aria-label=\"Interactive 3D viewport\"><div id=\"canvas\"></div><div class=\"viewport-label\"><i></i>DIMENSION</div><div class=\"view-actions\"><button id=\"frame\" title=\"Frame model (F)\">⛶</button><button id=\"spin\" title=\"Auto-rotate (R)\" aria-pressed=\"true\">⟳</button></div><div id=\"notice\" role=\"status\" hidden></div><div class=\"dock\" role=\"group\" aria-label=\"Rendering controls\"><button id=\"wire\" aria-pressed=\"false\">◇ Wireframe</button><button id=\"light\" aria-pressed=\"true\">☼ Lighting</button><button id=\"post\" aria-pressed=\"true\">✧ Processing</button><button id=\"clean\" aria-pressed=\"false\">Clean View</button></div></main><footer><div class=\"model\"><strong id=\"name\">Model</strong><span id=\"format\">3D</span><span id=\"count\"></span></div><div class=\"tips\"><span>Drag to orbit</span><span>Scroll to zoom</span></div></footer><dialog id=\"intro\"><h1>Dimension in FORGE</h1><p>Drag to orbit; scroll to zoom.</p></dialog><script>window.dimensionPreferences={spin:true,light:true,post:true,wire:false,clean:false,introSeen:true};</script><script type=\"module\" src=\"viewer.js\"></script><script>const model=new URLSearchParams(location.search).get(\"model\");const wait=setInterval(()=>{if(window.dimensionLoad){clearInterval(wait);window.dimensionLoad({url:model,name:decodeURIComponent(model.split('/').pop()),format:model.split('.').pop().toLowerCase()})}},25);</script></body></html>"""


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, ui_root: Path):
        self.ui_root = ui_root.resolve()
        self.token = secrets.token_urlsafe(24)
        self.models: dict[str, Path] = {}
        super().__init__(("127.0.0.1", 0), _Request)

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.server_port}/{self.token}/"

    def add_model(self, path: Path) -> str:
        key = secrets.token_urlsafe(16)
        self.models[key] = path.parent.resolve()
        return f"{self.base}model/{key}/{quote(path.name, safe='')}"


class _Request(BaseHTTPRequestHandler):
    server: _Server

    def log_message(self, *_args) -> None:
        pass

    def do_GET(self) -> None:  # noqa: N802 - HTTP handler API
        prefix = f"/{self.server.token}/"
        route = unquote(urlsplit(self.path).path)
        if not route.startswith(prefix):
            self.send_error(404)
            return
        relative = route[len(prefix):]
        if relative == "forge.html":
            payload = _FORGE_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)
            return
        root = self.server.ui_root
        if relative.startswith("model/"):
            _, _, remaining = relative.partition("/")
            key, _, relative = remaining.partition("/")
            root = self.server.models.get(key)
            if root is None:
                self.send_error(404)
                return
        try:
            asset = (root / relative).resolve()
            if not asset.is_relative_to(root) or not asset.is_file():
                raise ValueError("outside asset root")
            handle = asset.open("rb")
        except (OSError, ValueError):
            self.send_error(404)
            return
        with handle:
            mime = mimetypes.guess_type(asset.name)[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(asset.stat().st_size))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                self.wfile.write(handle.read())
            except (BrokenPipeError, ConnectionResetError):
                pass


class DimensionBridge:
    """Serve installed Dimension assets to embedded FORGE previews."""

    def __init__(self, ui_root: Path = DIMENSION_UI):
        self._ui_root = ui_root
        self._server: _Server | None = None

    @property
    def available(self) -> bool:
        return (self._ui_root / "index.html").is_file() and (self._ui_root / "viewer.js").is_file()

    def preview_url(self, path: Path) -> str:
        if not self.available or not path.is_file():
            return ""
        if self._server is None:
            self._server = _Server(self._ui_root)
            threading.Thread(target=self._server.serve_forever, daemon=True).start()
        model_url = self._server.add_model(path.resolve())
        return self._server.base + "forge.html?model=" + quote(model_url, safe="")

    def close(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
