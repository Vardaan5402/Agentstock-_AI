"""Safely reset AgentStock SQLite data while preserving the existing schema.

This administrative maintenance utility is deliberately explicit: it creates a
SQLite-consistent backup first, verifies it, and only runs deletion when called
with ``--execute``. It keeps the configured administrator's secure account
record so the Google-authenticated configured admin email retains ADMIN access.
"""
from __future__ import annotations

import argparse
import hashlib
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.config import get_admin_email, get_admin_password_hash


# Child/dependent records are deleted before their parent business/user rows.
# ``coupons`` is intentionally retained as platform configuration, while its
# user-specific redemption history is reset.
RESET_TABLES = (
    "coupon_redemptions",
    "supplier_products",
    "supplier_communications",
    "purchases",
    "sales_records",
    "decision_options",
    "outcomes",
    "what_if_scenarios",
    "decision_snapshots",
    "decisions",
    "policies",
    "uploaded_documents",
    "products",
    "suppliers",
    "businesses",
    "usage_records",
    "user_subscriptions",
    "user_policy_consents",
    "otp_codes",
    "audit_events",
    "admin_audit_events",
    "user_activity",
    "security_alerts",
    "razorpay_webhook_events",
)


def _schema_hash(connection: sqlite3.Connection) -> str:
    ddl = "\n".join(
        row[0] or ""
        for row in connection.execute(
            "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type, name"
        )
    )
    return hashlib.sha256(ddl.encode("utf-8")).hexdigest()


def _backup_database(source: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    target = source.with_name(f"{source.stem}_pre_reset_backup_{timestamp}{source.suffix}")
    if target.exists():
        raise RuntimeError("Refusing to overwrite an existing database backup.")

    with sqlite3.connect(source) as source_conn, sqlite3.connect(target) as backup_conn:
        source_conn.backup(backup_conn)

    with sqlite3.connect(target) as backup_conn:
        if backup_conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Database backup integrity verification failed.")
    return target


def reset_database(source: Path) -> tuple[Path, dict[str, int]]:
    if not source.is_file():
        raise FileNotFoundError(f"Database not found: {source}")

    admin_email = get_admin_email()
    admin_password_hash = get_admin_password_hash()
    if not admin_email or not admin_password_hash:
        raise RuntimeError(
            "ADMIN_EMAIL and ADMIN_PASSWORD_HASH must be configured before a production reset."
        )

    backup = _backup_database(source)
    with sqlite3.connect(source) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        schema_before = _schema_hash(connection)
        existing_admin = connection.execute(
            "SELECT id FROM users WHERE LOWER(email) = LOWER(?)", (admin_email,)
        ).fetchone()
        admin_id = existing_admin["id"] if existing_admin else "usr_admin_system"

        try:
            connection.execute("BEGIN IMMEDIATE")
            cleared = {}
            for table in RESET_TABLES:
                cursor = connection.execute(f"DELETE FROM {table}")
                cleared[table] = cursor.rowcount
            cleared["users"] = connection.execute("DELETE FROM users").rowcount
            connection.execute(
                """
                INSERT INTO users (
                    id, name, email, password_hash, role, is_verified,
                    is_locked, failed_login_attempts, onboarding_completed
                ) VALUES (?, ?, ?, ?, 'ADMIN', 1, 0, 0, 0)
                """,
                (admin_id, "Platform Administrator", admin_email, admin_password_hash),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise

        if _schema_hash(connection) != schema_before:
            raise RuntimeError("Schema changed during reset; the database was not accepted as reset.")
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Database integrity check failed after reset.")
        if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise RuntimeError("Foreign-key validation failed after reset.")
        if connection.execute("SELECT COUNT(*) FROM users WHERE id = ? AND role = 'ADMIN'", (admin_id,)).fetchone()[0] != 1:
            raise RuntimeError("Configured administrator was not preserved.")

    return backup, cleared


def main() -> None:
    parser = argparse.ArgumentParser(description="Back up and reset AgentStock SQLite data.")
    parser.add_argument("--database", default="agentstock.db", help="Path to the active SQLite database")
    parser.add_argument("--execute", action="store_true", help="Perform the reset after creating a verified backup")
    args = parser.parse_args()

    if not args.execute:
        raise SystemExit("No changes made. Re-run with --execute to create a backup and reset data.")

    backup, cleared = reset_database(Path(args.database).resolve())
    print(f"Backup created and verified: {backup}")
    print("Schema, integrity, and foreign-key checks passed.")
    for table, count in cleared.items():
        print(f"{table}: {count} rows cleared")
    print("Configured administrator account is present.")


if __name__ == "__main__":
    main()
