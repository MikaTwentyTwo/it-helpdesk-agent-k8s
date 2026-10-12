import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVENT_FILE = ROOT / "data" / "alert_notifications.jsonl"
EVENT_FILE.parent.mkdir(parents=True, exist_ok=True)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/health":
            self.send_error(404)
            return
        body = b'{"status":"ok"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/alerts":
            self.send_error(404)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 1048576:
                self.send_error(413)
                return
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("Expected JSON object")
        except (ValueError, json.JSONDecodeError):
            self.send_error(400)
            return

        event = {
            "received_at": datetime.now(timezone.utc).isoformat(),
            "notification": payload,
        }
        with EVENT_FILE.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")

        print(
            "Notification:",
            payload.get("status"),
            "alerts:",
            len(payload.get("alerts", [])),
            flush=True,
        )
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()


if __name__ == "__main__":
    print("Alert receiver listening on port 8082", flush=True)
    ThreadingHTTPServer(("0.0.0.0", 8082), Handler).serve_forever()
