"""Explicitly migrate the supplied seed's eight-digit plaintext passwords to Argon2."""

import argparse
import re

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.database import get_engine
from app.models import User
from app.security import hash_password


def migrate_passwords(db: Session, apply: bool) -> tuple[int, int]:
    converted = 0
    skipped = 0
    for user in db.scalars(select(User)).all():
        # Existing hashes are preserved. Only the documented seed format is migrated.
        if not re.fullmatch(r"[0-9]{8}", user.password):
            skipped += 1
            continue
        if not apply:
            converted += 1
            continue
        old_password = user.password
        result = db.execute(
            update(User)
            .where(User.username == user.username, User.password == old_password)
            .values(password=hash_password(old_password))
            .execution_options(synchronize_session=False)
        )
        if result.rowcount == 1:
            converted += 1
        else:
            skipped += 1
    if apply:
        db.commit()
    return converted, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Commit password hash changes to MySQL")
    args = parser.parse_args()
    with Session(get_engine()) as db:
        count, skipped = migrate_passwords(db, apply=args.apply)
    action = "Converted" if args.apply else "Would convert (dry run)"
    print(f"{action}: {count}. Skipped: {skipped}. No passwords are printed.")


if __name__ == "__main__":
    main()
