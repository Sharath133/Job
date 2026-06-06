from __future__ import annotations

import argparse
import json
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow


SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a Gmail API refresh token from a Google OAuth Desktop client JSON file."
    )
    parser.add_argument(
        "client_json",
        help="Path to the downloaded OAuth Desktop client JSON file from Google Cloud.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="Local callback port. Use 0 to pick a free port automatically.",
    )
    args = parser.parse_args()

    client_path = Path(args.client_json)
    if not client_path.is_file():
        raise SystemExit(f"OAuth client JSON file not found: {client_path}")

    raw_client = json.loads(client_path.read_text(encoding="utf-8"))
    client_section = raw_client.get("installed") or raw_client.get("web") or {}
    client_id = client_section.get("client_id", "")
    client_secret = client_section.get("client_secret", "")
    if not client_id or not client_secret:
        raise SystemExit("OAuth JSON must contain client_id and client_secret.")

    flow = InstalledAppFlow.from_client_secrets_file(str(client_path), SCOPES)
    credentials = flow.run_local_server(
        port=args.port,
        access_type="offline",
        prompt="consent",
    )

    if not credentials.refresh_token:
        raise SystemExit(
            "Google did not return a refresh token. Re-run this script with the same account, "
            "or revoke the app access from your Google account and try again."
        )

    print("\nAdd these values to GitHub Actions secrets and local .env:\n")
    print(f"GMAIL_API_CLIENT_ID={client_id}")
    print(f"GMAIL_API_CLIENT_SECRET={client_secret}")
    print(f"GMAIL_API_REFRESH_TOKEN={credentials.refresh_token}")
    print("\nKeep these values private. Do not commit them.\n")


if __name__ == "__main__":
    main()
