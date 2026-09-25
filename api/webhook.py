import json

from http.server import BaseHTTPRequestHandler

from ahigao_bot import process_update


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

        self.wfile.write(
            json.dumps({
                "ok": True,
                "message": "Ahigao webhook is alive"
            }).encode()
        )

    def do_POST(self):
        try:
            content_length = int(
                self.headers.get("Content-Length", "0")
            )

            body = self.rfile.read(content_length)

            update = json.loads(body)

            import asyncio

            asyncio.run(
                process_update(update)
            )

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()

            self.wfile.write(
                b'{"ok":true}'
            )

        except Exception as e:
            print(f"Webhook error: {e}")

            # Telegram должен получить 200,
            # чтобы не долбить webhook бесконечными ретраями.
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()

            self.wfile.write(
                json.dumps({
                    "ok": False,
                    "error": str(e)
                }).encode()
            )