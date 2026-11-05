# ==============================================================================
# TECH STACK: [Data Migration Tool]
# Migrates accounts from legacy users_data.json and platform_stats.json to PostgreSQL
# ==============================================================================
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Add backend directory to path if run standalone
_BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_BACKEND_DIR))

from database import get_db_session, init_db, is_database_configured
from logger import logger
from models import PlatformMetric, User


def migrate_json_to_database(json_path: Path | None = None, dry_run: bool = False) -> dict[str, int]:
    """
    Imports accounts from users_data.json into the target PostgreSQL or SQLite database.
    Idempotent: skips users whose email is already present.
    """
    file_path = json_path or (_BACKEND_DIR / "users_data.json")
    if not file_path.is_file():
        logger.warning(f"[Migration] JSON source file '{file_path}' does not exist. Nothing to migrate.")
        return {"scanned": 0, "inserted": 0, "skipped": 0}

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
        users = data.get("users", {})
    except Exception as exc:
        logger.error(f"[Migration] Failed to parse JSON source file: {exc}")
        return {"scanned": 0, "inserted": 0, "skipped": 0}

    if not is_database_configured():
        logger.error("[Migration] Target database is not configured. Set DATABASE_URL environment variable.")
        return {"scanned": len(users), "inserted": 0, "skipped": len(users)}

    init_db()

    scanned = 0
    inserted = 0
    skipped = 0

    with get_db_session() as session:
        for email, udata in users.items():
            scanned += 1
            clean_email = str(email).strip().lower()
            existing = session.query(User).filter_by(email=clean_email).first()
            if existing:
                skipped += 1
                continue

            if dry_run:
                inserted += 1
                continue

            new_user = User(
                name=udata.get("name", "User"),
                email=clean_email,
                phone=udata.get("phone", ""),
                salt=udata.get("salt", ""),
                password_hash=udata.get("password_hash", ""),
                created_at=int(udata.get("created_at", 0)),
            )
            session.add(new_user)
            inserted += 1

        # Migrate platform stats if available
        stats_file = _BACKEND_DIR / "platform_stats.json"
        if stats_file.is_file() and not dry_run:
            try:
                stats_data = json.loads(stats_file.read_text(encoding="utf-8"))
                total_analyses = int(stats_data.get("total_analyses", 0))
                metric = session.query(PlatformMetric).filter_by(metric_key="total_analyses").first()
                if metric:
                    metric.metric_value = max(metric.metric_value, total_analyses)
                else:
                    session.add(PlatformMetric(metric_key="total_analyses", metric_value=total_analyses))
            except Exception:
                pass

    logger.info(
        f"[Migration] Complete. Scanned: {scanned}, Inserted: {inserted}, Skipped (already existed): {skipped}"
    )
    return {"scanned": scanned, "inserted": inserted, "skipped": skipped}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate local users_data.json to cloud PostgreSQL")
    parser.add_argument("--dry-run", action="store_true", help="Simulate migration without committing changes")
    parser.add_argument("--file", type=str, default="", help="Path to custom users_data.json file")
    args = parser.parse_args()

    custom_path = Path(args.file) if args.file else None
    results = migrate_json_to_database(json_path=custom_path, dry_run=args.dry_run)
    print(f"Migration summary: {results}")
