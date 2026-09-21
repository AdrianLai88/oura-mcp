"""One-time script: completes Oura OAuth2 flow and prints the refresh token."""
import http.server
import threading
import urllib.parse
import urllib.request
import json
import webbrowser
import os
import ssl

_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE

CLIENT_ID = os.environ["OURA_CLIENT_ID"]
CLIENT_SECRET = os.environ["OURA_CLIENT_SECRET"]
REDIRECT_URI = "http://localhost:8080"
SCOPES = "email daily tag session ring_configuration heartrate workout personal spo2 stress heart_health"

code_holder = {}

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = dict(urllib.parse.parse_qsl(parsed.query))
        if "code" in params:
            code_holder["code"] = params["code"]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Got it. You can close this tab.")
        else:
            self.send_response(400)
            self.end_headers()

    def log_message(self, *args):
        pass

server = http.server.HTTPServer(("localhost", 8080), Handler)
thread = threading.Thread(target=server.serve_forever)
thread.daemon = True
thread.start()

auth_url = (
    "https://cloud.ouraring.com/oauth/authorize"
    f"?response_type=code&client_id={CLIENT_ID}"
    f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
    f"&scope={urllib.parse.quote(SCOPES)}"
)

print("Opening browser for Oura authorization...")
webbrowser.open(auth_url)
print("Waiting for callback (log in to Oura in the browser)...")

import time
while "code" not in code_holder:
    time.sleep(0.2)

server.shutdown()
code = code_holder["code"]

data = urllib.parse.urlencode({
    "grant_type": "authorization_code",
    "code": code,
    "redirect_uri": REDIRECT_URI,
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
}).encode()

req = urllib.request.Request(
    "https://api.ouraring.com/oauth/token",
    data=data,
    headers={"Content-Type": "application/x-www-form-urlencoded"},
)
with urllib.request.urlopen(req, context=_ctx) as resp:
    tokens = json.loads(resp.read())

print("\n✓ Success! Add this to Railway as OURA_REFRESH_TOKEN:")
print(tokens["refresh_token"])
