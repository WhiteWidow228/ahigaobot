import json

from http.server import BaseHTTPRequestHandler

from ahigao_bot import send_klitor_time


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        import asyncio

        try:
            asyncio.run(send_klitor_time())

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()

            self.wfile.write(
                b'{"ok":true,"message":"12:28 sent"}'
            )

        except Exception as e:
            print(f"Klitor cron error: {e}")

            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()

            self.wfile.write(
                json.dumps({
                    "ok": False,
                    "error": str(e)
                }).encode()
            )