
import base64
import hashlib
import json
import secrets
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

BASE_URL = "http://127.0.0.1:8000"
REDIRECT_URI = "http://localhost:8765/callback"

result = {}


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = urllib.parse.parse_qs(
            urllib.parse.urlparse(self.path).query
        )

        result["code"] = query.get("code", [None])[0]
        result["state"] = query.get("state", [None])[0]
        result["error"] = query.get("error", [None])[0]

        message = (
            "OAuth callback received. You may return to VS Code."
            if result["code"]
            else "OAuth callback did not contain an authorization code."
        )

        body = message.encode()
        self.send_response(200 if result["code"] else 400)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def post_json(url, payload):
    data = json.dumps(payload).encode()
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode())


def post_form(url, payload):
    data = urllib.parse.urlencode(payload).encode()
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode())


def main():
    # Create a fresh PKCE verifier and challenge.
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).decode().rstrip("=")
    state = secrets.token_urlsafe(24)

    # Register a temporary OAuth client.
    client = post_json(
        f"{BASE_URL}/register",
        {
            "client_name": "Local OAuth Flow Test",
            "redirect_uris": [REDIRECT_URI],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "client_secret_post",
        },
    )

    client_id = client["client_id"]
    client_secret = client.get("client_secret")

    print("PASS: Temporary OAuth client registered")

    # Start the local callback listener.
    callback_server = HTTPServer(
        ("127.0.0.1", 8765), CallbackHandler
    )
    callback_server.timeout = 180

    listener = threading.Thread(
        target=callback_server.handle_request,
        daemon=True,
    )
    listener.start()

    # Open the authorization page.
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
    }

    login_url = (
        f"{BASE_URL}/authorize?"
        + urllib.parse.urlencode(params)
    )

    print("Opening the browser for login...")
    webbrowser.open(login_url)

    print("Please complete login in the browser.")
    listener.join(timeout=185)
    callback_server.server_close()

    if not result.get("code"):
        raise RuntimeError(
            "No authorization code received. "
            "Check the browser and server terminal."
        )

    if result.get("state") != state:
        raise RuntimeError("OAuth state did not match.")

    if result.get("error"):
        raise RuntimeError(f"OAuth authorization failed: {result['error']}")

    print("PASS: Browser callback and state validation")

    # Exchange the code for tokens.
    token_request = {
        "grant_type": "authorization_code",
        "code": result["code"],
        "redirect_uri": REDIRECT_URI,
        "client_id": client_id,
        "code_verifier": verifier,
    }

    if client_secret:
        token_request["client_secret"] = client_secret

    tokens = post_form(f"{BASE_URL}/token", token_request)

    if not tokens.get("access_token"):
        raise RuntimeError("Token response did not contain an access token.")

    print("PASS: Authorization code exchanged for access token")
    print("Refresh token returned:", bool(tokens.get("refresh_token")))
    print("\nOAuth flow test completed successfully.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nTEST DID NOT COMPLETE: {type(exc).__name__}: {exc}")
        print("Do not share any credentials or tokens.")
