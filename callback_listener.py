
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if parsed.path != "/callback":
            self.send_error(404)
            return

        code = params.get("code", [None])[0]
        state = params.get("state", [None])[0]
        error = params.get("error", [None])[0]

        if error:
            message = f"Authorization failed: {error}"
            status = 400
        elif code and state:
            message = (
                "Callback received successfully. "
                "The authorization code is ready for testing."
            )
            status = 200
        else:
            message = "Callback received, but code or state is missing."
            status = 400

        body = message.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

        print("\nCallback received.")
        print("Authorization code received:", bool(code))
        print("State received:", bool(state))
        print("Error received:", bool(error))

    def log_message(self, format, *args):
        print("Callback listener:", format % args)


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", 8765), CallbackHandler)
    print("Callback listener ready at http://localhost:8765/callback")
    print("Keep this terminal open while testing.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nCallback listener stopped.")
    finally:
        server.server_close()
