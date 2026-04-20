import sqlite3
import os
import json
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

DEFAULT_DB_PATH = os.getenv("DB_PATH", os.path.join(os.getcwd(), "data/data.db"))


class DB:
    def __init__(self, path: str = DEFAULT_DB_PATH):
        self.path = path
        # Ensure directory exists (skip for in-memory databases)
        if self.path != ":memory:":
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.init()

    def init(self):
        self.conn.execute("PRAGMA foreign_keys = ON")
        try:
            self.conn.execute(
                "ALTER TABLE installations ADD COLUMN last_accessed_at DATETIME"
            )
            self.conn.commit()
        except Exception:
            pass

    def _apply_schema(self):
        """Apply the database schema idempotently (all statements use IF NOT EXISTS)."""
        schema = """
            CREATE TABLE IF NOT EXISTS currency (
                id integer not null primary key autoincrement,
                code text not null,
                name text,
                symbol text,
                crypto bool not null default true
            );
            CREATE TABLE IF NOT EXISTS rate (
                date DATE not null,
                currency_id references currency(id),
                value real not null,
                timestamp DATETIME default CURRENT_TIMESTAMP,
                UNIQUE(date, currency_id)
            );
            CREATE VIEW IF NOT EXISTS rates AS
                SELECT date, currency.id, currency.code, value, timestamp
                FROM rate LEFT JOIN currency ON rate.currency_id = currency.id;
            CREATE INDEX IF NOT EXISTS idx_rate_date_currency_id ON rate(date, currency_id);
            CREATE INDEX IF NOT EXISTS idx_rate_date ON rate(date);
            CREATE TABLE IF NOT EXISTS packages (
                id TEXT NOT NULL PRIMARY KEY,
                sender_id TEXT NOT NULL,
                iv TEXT NOT NULL,
                ciphertext TEXT NOT NULL,
                recipient_keys TEXT NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS package_recipients (
                package_id TEXT NOT NULL REFERENCES packages(id) ON DELETE CASCADE,
                installation_id TEXT NOT NULL,
                encrypted_key TEXT NOT NULL,
                PRIMARY KEY (package_id, installation_id)
            );
            CREATE INDEX IF NOT EXISTS idx_package_recipients_installation ON package_recipients(installation_id);
            CREATE INDEX IF NOT EXISTS idx_packages_updated_at ON packages(updated_at);
            CREATE TABLE IF NOT EXISTS installations (
                timestamp DATETIME not null default CURRENT_TIMESTAMP,
                uuid text not null primary key,
                jwt text not null,
                installations integer not null default 1
            );
            CREATE TABLE IF NOT EXISTS handshake (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                uuid TEXT REFERENCES installations(uuid) NOT NULL,
                msg TEXT NOT NULL,
                created_at INTEGER NOT NULL DEFAULT (unixepoch(CURRENT_TIMESTAMP))
            );
        """
        # SQLite doesn't support multiple statements in one execute() call;
        # split on semicolons and run each non-empty statement individually.
        for statement in schema.split(";"):
            stmt = statement.strip()
            if stmt:
                self.conn.execute(stmt)
        self.conn.commit()

    def save_rates(self, rates: Dict[str, float], date: Optional[str] = None):
        target_date = date or datetime.now().strftime("%Y-%m-%d")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor = self.conn.cursor()
        sql = """
            INSERT OR REPLACE INTO rate (date, currency_id, value, timestamp)
            VALUES (?, (SELECT id FROM currency WHERE UPPER(code) = UPPER(?)), ?, ?)
        """

        for currency, value in rates.items():
            cursor.execute(sql, (target_date, currency, value, timestamp))

        self.conn.commit()

    def has_data_for_date(self, date: str) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("SELECT 1 FROM rate WHERE date = ? LIMIT 1", (date,))
        return cursor.fetchone() is not None

    def get_currencies(self, crypto: Optional[bool] = None) -> List[Dict[str, Any]]:
        query = "SELECT * FROM currency"
        params = []
        if crypto is not None:
            query += " WHERE crypto = ?"
            params.append(1 if crypto else 0)

        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_rates_for_date(
        self, date: str, currencies: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        query = "SELECT code, value, timestamp, date FROM rates WHERE date = ?"
        params = [date]

        if currencies:
            placeholders = ",".join(["?"] * len(currencies))
            query += f" AND UPPER(code) IN ({placeholders})"
            params.extend([c.upper() for c in currencies])

        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_latest_rates(self, currencies: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        # Find the latest date first
        cursor = self.conn.cursor()
        cursor.execute("SELECT date FROM rate ORDER BY date DESC LIMIT 1")
        last_date_row = cursor.fetchone()

        if not last_date_row:
            return []

        latest_date = last_date_row["date"]
        return self.get_rates_for_date(latest_date, currencies)

    def get_installation_by_uuid(self, uuid: str) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM installations WHERE uuid = ?", (uuid,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def add_installation(self, uuid: str, jwt: str, installations: int = 1) -> None:
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO installations (uuid, jwt, installations) VALUES (?, ?, ?)",
            (uuid, jwt, installations),
        )
        self.conn.commit()

    def increment_installation_count(self, uuid: str) -> None:
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE installations SET installations = installations + 1 WHERE uuid = ?",
            (uuid,),
        )
        self.conn.commit()

    def update_installation_jwt(self, uuid: str, jwt: str) -> None:
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE installations SET jwt = ? WHERE uuid = ?",
            (jwt, uuid),
        )
        self.conn.commit()

    def get_installation_by_jwt(self, jwt: str) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM installations WHERE jwt = ?", (jwt,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def touch_installation(self, jwt: str) -> None:
        self.conn.execute(
            "UPDATE installations SET last_accessed_at = CURRENT_TIMESTAMP WHERE jwt = ?",
            (jwt,),
        )
        self.conn.commit()

    def save_package(
        self,
        sender_id: str,
        iv: str,
        ciphertext: str,
        recipient_keys: List[Dict[str, str]],
    ) -> str:
        """Save an encrypted package and return its ID."""
        package_id = str(uuid.uuid4())
        cursor = self.conn.cursor()

        # Store the package
        params = (package_id, sender_id, iv, ciphertext, json.dumps(recipient_keys))
        cursor.execute(
            """INSERT INTO packages (id, sender_id, iv, ciphertext, recipient_keys)
        VALUES (?, ?, ?, ?, ?)""",
            params,
        )

        # Store recipient mappings for efficient querying
        for recipient in recipient_keys:
            params = (
                package_id,
                recipient["installation_id"],
                recipient["encrypted_key"],
            )
            cursor.execute(
                """INSERT INTO
                        package_recipients
                        (package_id, installation_id, encrypted_key)
                   VALUES (?, ?, ?)""",
                params,
            )

        self.conn.commit()
        return package_id

    def get_packages_for_installation(
        self, installation_id: str, since: int
    ) -> List[Dict[str, Any]]:
        """Get all packages for an installation since a timestamp (milliseconds)."""
        cursor = self.conn.cursor()

        # Convert milliseconds to datetime
        since_datetime = datetime.fromtimestamp(since / 1000.0).strftime("%Y-%m-%d %H:%M:%S.%f")

        query = """
            SELECT DISTINCT
                p.id, p.sender_id, p.iv, p.ciphertext, p.recipient_keys
            FROM packages p
            JOIN package_recipients pr ON p.id = pr.package_id
            WHERE pr.installation_id = ? AND p.updated_at > ?
            ORDER BY p.updated_at ASC
        """

        cursor.execute(query, (installation_id, since_datetime))
        rows = cursor.fetchall()

        packages = []
        for row in rows:
            packages.append(
                {
                    "id": row["id"],
                    "package": {
                        "sender_id": row["sender_id"],
                        "iv": row["iv"],
                        "ciphertext": row["ciphertext"],
                        "recipient_keys": json.loads(row["recipient_keys"]),
                    },
                }
            )

        return packages

    def delete_packages(self, package_ids: List[str], installation_id: str) -> None:
        """Remove acking device's recipient rows, then clean up orphaned packages."""
        if not package_ids:
            return

        cursor = self.conn.cursor()
        placeholders = ",".join(["?"] * len(package_ids))

        # Step 1: remove only this device's recipient rows
        cursor.execute(
            f"DELETE FROM package_recipients WHERE package_id IN ({placeholders}) AND installation_id = ?",
            package_ids + [installation_id],
        )

        # Step 2: delete packages that have no remaining recipients
        cursor.execute(
            "DELETE FROM packages WHERE id NOT IN (SELECT DISTINCT package_id FROM package_recipients)"
        )

        self.conn.commit()

    def save_handshake(self, uuid: str, payload: str):
        """Save data to handshake"""
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO handshake (uuid, msg) values (?, ?)", (uuid, payload))
        self.conn.commit()

    def get_handshake(self, uuid: str):
        """Get all data from handshake for uuid"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, msg, created_at FROM handshake WHERE uuid = ?", (uuid,))
        rows = cursor.fetchall()
        packages = []
        for row in rows:
            packages.append(
                {
                    "id": row["id"],
                    "payload": row["msg"],
                    "created_at": row["created_at"],
                }
            )

        return packages

    def delete_handshake(self, ids: List[int], uuid: str):
        """Delete data from handshake by id and uuid"""
        cursor = self.conn.cursor()
        placeholders = ",".join(["?"] * len(ids))
        cursor.execute(
            f"DELETE FROM handshake WHERE id IN ({placeholders}) AND uuid = ?", (*ids, uuid)
        )
        self.conn.commit()

    def close(self):
        self.conn.close()


# Singleton instance
db = DB()
