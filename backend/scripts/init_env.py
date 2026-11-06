"""Generate local .env with a random signing key without overwriting an existing file."""

import secrets
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def main() -> None:
    target = BACKEND_DIR / ".env"
    content = (BACKEND_DIR / ".env.example").read_text(encoding="utf-8")
    content = content.replace("JWT_SECRET_KEY=\n", f"JWT_SECRET_KEY={secrets.token_urlsafe(48)}\n")
    try:
        with target.open("x", encoding="utf-8") as stream:
            stream.write(content)
    except FileExistsError:
        print(".env already exists; no changes made.")
        return
    print("Created .env. Edit DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD and DB_SSL before connecting.")


if __name__ == "__main__":
    main()
