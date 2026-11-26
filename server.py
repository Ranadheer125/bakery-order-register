"""Bakery Order Register - web server (Python standard library only).
Run:  python server.py   then open http://localhost:8000
"""
import json, os, re, threading
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from core import *
from core import LOCK, BASE
STATIC = os.path.join(BASE, "static")

# ---------- HTTP ----------
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, code, body, ctype="application/json", extra=None):
        b = body if isinstance(body, bytes) else (body if isinstance(body, str) else json.dumps(body)).encode()
        self.send_response(code); self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        for k, v in (extra or {}).items(): self.send_header(k, v)
        self.end_headers(); self.wfile.write(b)
    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n).decode("utf-8") if n else ""
    def json_body(self):
        try:
            d = json.loads(self.body() or "{}"); return d if isinstance(d, dict) else {}
        except json.JSONDecodeError: return {}
    def oid(self, path):
        m = re.fullmatch(r"/api/orders/(\d+)", path); return int(m.group(1)) if m else None

    def do_GET(self):
        u = urlparse(self.path); qs = {k: v[0] for k, v in parse_qs(u.query).items()}
        if u.path == "/api/orders":
            with LOCK: return self.send(200, search(load(), qs.get("q", ""), qs.get("status", ""), qs.get("category", ""), qs.get("pickup", "")))
        if u.path == "/api/summary":
            with LOCK: return self.send(200, summary(load()))
        if u.path == "/api/meta": return self.send(200, {"categories": CATEGORIES})
        if u.path == "/api/export":
            with LOCK: text, ct, name = export(load(), qs.get("fmt", "csv"))
            return self.send(200, text, ct, {"Content-Disposition": f'attachment; filename="{name}"'})
        path = "/index.html" if u.path == "/" else u.path
        fp = os.path.normpath(os.path.join(STATIC, path.lstrip("/")))
        if not fp.startswith(STATIC) or not os.path.isfile(fp): return self.send(404, {"error": "Not found"})
        ct = {"html": "text/html", "css": "text/css", "js": "application/javascript"}.get(fp.rsplit(".", 1)[-1], "application/octet-stream")
        with open(fp, "rb") as f: self.send(200, f.read(), ct)

    def do_POST(self):
        u = urlparse(self.path)
        with LOCK:
            orders = load()
            if u.path == "/api/orders":
                try: o = validate(self.json_body())
                except ValidationError as ve: return self.send(400, {"errors": ve.errors})
                o["id"] = max((x["id"] for x in orders), default=0) + 1
                orders.append(o); save(orders); return self.send(201, o)
            if u.path == "/api/import":
                added, log = bulk_import(orders, self.body()); save(orders)
                return self.send(200, {"added": added, "errors": log})
            if u.path == "/api/reset":
                save(seed_orders()); return self.send(200, {"ok": True})
        self.send(404, {"error": "Not found"})

    def do_PUT(self):
        i = self.oid(urlparse(self.path).path)
        if i is None: return self.send(404, {"error": "Not found"})
        with LOCK:
            orders = load(); cur = next((o for o in orders if o["id"] == i), None)
            if not cur: return self.send(404, {"error": "Order not found"})
            try: new = validate({**cur, **self.json_body()})
            except ValidationError as ve: return self.send(400, {"errors": ve.errors})
            cur.update(new); save(orders); self.send(200, cur)

    def do_DELETE(self):
        i = self.oid(urlparse(self.path).path)
        if i is None: return self.send(404, {"error": "Not found"})
        with LOCK:
            orders = load(); keep = [o for o in orders if o["id"] != i]
            if len(keep) == len(orders): return self.send(404, {"error": "Order not found"})
            save(keep); self.send(200, {"deleted": i})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    with LOCK: load()
    print(f"Bakery Order Register running at http://localhost:{port}  (Ctrl+C to stop)")
    try: ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
    except KeyboardInterrupt: print("\nStopped.")
