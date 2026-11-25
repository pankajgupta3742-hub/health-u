"""Serves the built frontend and forwards /api requests to the Health-U API.

Use this for the preview (or any single-server test) so the browser talks to one origin and CORS is not needed.

    cd frontend && npm run build
    python3 scripts/serve_preview.py --port 4173 --api http://127.0.0.1:8000

Static files come from frontend/dist. Any path that is not a file gets index.html (single-page app).
Requests starting with /api/ are forwarded unchanged (method, headers, body) and the response is returned as is.
"""
import argparse
import http.client
import os
import posixpath
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

HOP_BY_HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers",
              "transfer-encoding", "upgrade", "content-length"}

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
API_HOST = "127.0.0.1"
API_PORT = 8000


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    # ---- API proxy -------------------------------------------------------
    def _proxy(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_BY_HOP | {"host"}}
        try:
            conn = http.client.HTTPConnection(API_HOST, API_PORT, timeout=120)
            conn.request(self.command, self.path, body=body, headers=headers)
            resp = conn.getresponse()
            data = resp.read()
        except OSError as e:
            msg = f'{{"detail":"The Health-U API is not running ({e.__class__.__name__})."}}'.encode()
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)
            return
        # One line per API call: status, method, path, and the caller's address. Use it to diagnose sign-outs.
        print(f"{self.client_address[0]} {self.command} {self.path.split('?')[0]} -> {resp.status}", flush=True)
        self.send_response(resp.status, resp.reason)
        for k, v in resp.getheaders():
            if k.lower() not in HOP_BY_HOP:
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        try:
            if self.command != "HEAD":
                self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass  # the browser closed the connection early (page reload or navigation); nothing to send
        finally:
            conn.close()

    def do_GET(self):
        if self.path.startswith("/api/"):
            return self._proxy()
        path = urlsplit(self.path).path
        if not os.path.exists(self._fs_path(path)) or os.path.isdir(self._fs_path(path)) and not os.path.exists(os.path.join(self._fs_path(path), "index.html")):
            if "." not in posixpath.basename(path):
                self.path = "/index.html"
        return super().do_GET()

    def do_HEAD(self):
        return self.do_GET()

    def do_POST(self):
        return self._proxy() if self.path.startswith("/api/") else self.send_error(404)

    def do_DELETE(self):
        return self._proxy() if self.path.startswith("/api/") else self.send_error(404)

    def do_PUT(self):
        return self._proxy() if self.path.startswith("/api/") else self.send_error(404)

    def do_OPTIONS(self):
        return self._proxy() if self.path.startswith("/api/") else self.send_error(404)

    def _fs_path(self, url_path):
        return os.path.join(ROOT, *[p for p in posixpath.normpath(unquote(url_path)).split("/") if p and p not in (".", "..")])

    def log_message(self, fmt, *args):  # quieter logs
        super().log_message(fmt, *args)


def main():
    global API_HOST, API_PORT
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=4173)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    args = ap.parse_args()
    u = urlsplit(args.api)
    API_HOST, API_PORT = u.hostname or "127.0.0.1", u.port or 8000
    if not os.path.isdir(ROOT):
        raise SystemExit(f"Build the frontend first: {ROOT} is missing")
    print(f"Serving {ROOT} on http://{args.host}:{args.port} and forwarding /api to {API_HOST}:{API_PORT}", flush=True)
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
