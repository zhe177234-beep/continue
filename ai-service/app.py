"""Single-user local demo server. Not an Internet-facing production server."""
import base64
import binascii
import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from engine import Engine, MAX_FILE

ROOT = Path(__file__).resolve().parent.parent


def handler_for(engine):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(30)

        def send(self, status, value, content_type="application/json; charset=utf-8"):
            data = json.dumps(value, ensure_ascii=False).encode() if content_type.startswith("application/json") else value
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(data)

        def authorized(self):
            token = os.getenv("APP_TOKEN", "")
            if token and not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + token):
                self.send(401, {"error": "请输入正确的访问令牌"})
                return False
            return True

        def do_GET(self):
            path = urlsplit(self.path).path
            if path in {"/", "/app.js", "/style.css"}:
                name = {"/": "index.html", "/app.js": "app.js", "/style.css": "style.css"}[path]
                mime = {"/": "text/html", "/app.js": "text/javascript", "/style.css": "text/css"}[path]
                return self.send(200, (ROOT / "web" / name).read_bytes(), mime + "; charset=utf-8")
            if not self.authorized():
                return
            if path == "/api/health":
                self.send(200, {"status": "ok", "answer_kind": "extractive"})
            elif path == "/api/documents":
                self.send(200, engine.documents())
            elif path == "/api/graph":
                self.send(200, engine.graph())
            else:
                self.send(404, {"error": "接口不存在"})

        def do_POST(self):
            if not self.authorized():
                return
            # Restrict browser cross-origin mutations without requiring CORS.
            if self.headers.get("Sec-Fetch-Site") == "cross-site":
                return self.send(403, {"error": "不允许跨站请求"})
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                return self.send(415, {"error": "请使用 application/json"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_FILE * 2:
                    return self.send(413, {"error": "请求为空或过大"})
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError("请求应为 JSON 对象")
                path = urlsplit(self.path).path
                if path == "/api/documents":
                    if not isinstance(body.get("name"), str) or not isinstance(body.get("data"), str):
                        raise ValueError("缺少文件名或 base64 文件内容")
                    result = engine.ingest(body["name"], base64.b64decode(body["data"], validate=True))
                elif path == "/api/ask":
                    result = engine.answer(body.get("question"), body.get("mode", "auto"), body.get("k", 5))
                elif path == "/api/documents/delete":
                    if not isinstance(body.get("id"), str):
                        raise ValueError("缺少文档 ID")
                    result = {"deleted": engine.delete(body["id"])}
                else:
                    return self.send(404, {"error": "接口不存在"})
                self.send(200, result)
            except (ValueError, TypeError, binascii.Error, UnicodeError):
                self.send(400, {"error": "请求或文件无效，请检查编码、字段、大小和检索参数"})
            except Exception:
                self.log_error("request failed")
                self.send(500, {"error": "服务处理失败，请检查服务日志及数据目录"})

    return Handler


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    if host not in {"127.0.0.1", "localhost", "::1"} and len(os.getenv("APP_TOKEN", "")) < 16:
        raise SystemExit("对外监听必须配置至少 16 字符的 APP_TOKEN")
    engine = Engine(os.getenv("DB_PATH", str(ROOT / "data" / "knowledge.db")))
    server = ThreadingHTTPServer((host, int(os.getenv("PORT", "8000"))), handler_for(engine))
    server.timeout = 30
    print(f"智学本地演示：http://{host}:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
