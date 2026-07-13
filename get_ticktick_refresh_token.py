#!/usr/bin/env python3
"""
Run this ONCE, locally on your own computer, to get a TICKTICK_REFRESH_TOKEN.
You do not need to run this again afterwards - the refresh token is reused
by the GitHub Actions workflow indefinitely (TickTick refresh tokens don't expire
from normal use).

Steps:
1. Go to https://developer.ticktick.com/manage and register an app.
   - Set the redirect URI to: http://localhost:8000/callback
   - Note down your Client ID and Client Secret.
2. Fill in CLIENT_ID and CLIENT_SECRET below.
3. Run: python get_ticktick_refresh_token.py
4. It opens your browser to authorize. Log in and approve.
5. It will print your refresh token - copy it into your GitHub secrets.
"""

import http.server
import urllib.parse
import webbrowser

import requests

CLIENT_ID = "PASTE_YOUR_CLIENT_ID_HERE"
CLIENT_SECRET = "PASTE_YOUR_CLIENT_SECRET_HERE"
REDIRECT_URI = "http://localhost:8000/callback"

auth_code = {}


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        if "code" in params:
            auth_code["code"] = params["code"][0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Authorized! You can close this tab and return to the terminal.")
        else:
            self.send_response(400)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # silence default logging


def main():
    if "PASTE_YOUR" in CLIENT_ID or "PASTE_YOUR" in CLIENT_SECRET:
        raise SystemExit("Edit this file first and paste in your CLIENT_ID / CLIENT_SECRET")

    auth_url = (
        "https://ticktick.com/oauth/authorize?"
        + urllib.parse.urlencode(
            {
                "client_id": CLIENT_ID,
                "scope": "tasks:write tasks:read",
                "state": "binreminder",
                "redirect_uri": REDIRECT_URI,
                "response_type": "code",
            }
        )
    )
    print(f"Opening browser to authorize:\n{auth_url}\n")
    webbrowser.open(auth_url)

    server = http.server.HTTPServer(("localhost", 8000), CallbackHandler)
    print("Waiting for authorization...")
    while "code" not in auth_code:
        server.handle_request()

    resp = requests.post(
        "https://ticktick.com/oauth/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": auth_code["code"],
            "grant_type": "authorization_code",
            "scope": "tasks:write tasks:read",
            "redirect_uri": REDIRECT_URI,
        },
    )
    resp.raise_for_status()
    tokens = resp.json()

    expires_in_seconds = tokens.get("expires_in")
    expiry_note = ""
    if expires_in_seconds:
        from datetime import datetime, timedelta
        expiry_date = datetime.now() + timedelta(seconds=expires_in_seconds)
        expiry_note = f" (expires around {expiry_date.strftime('%d %B %Y')})"

    print("\nSuccess! TickTick did not return a refresh token - it issues a")
    print("single long-lived access token instead. Here it is:\n")
    print(f"TICKTICK_ACCESS_TOKEN = {tokens['access_token']}{expiry_note}")
    print("\nSave this as a GitHub secret named TICKTICK_ACCESS_TOKEN.")
    print("You'll need to re-run this script to get a new one once it expires.")


if __name__ == "__main__":
    main()
