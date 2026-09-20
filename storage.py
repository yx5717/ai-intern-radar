from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from cryptography.fernet import Fernet, InvalidToken


PASSWORD_ITERATIONS = 600_000


class UserStore:
    def __init__(self, db_path: Path, key_path: Path) -> None:
        self.db_path = Path(db_path)
        self.key_path = Path(key_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _init_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password_salt TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS user_state (
                    user_id INTEGER PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    api_key_encrypted TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    user_id INTEGER NOT NULL,
                    record_id TEXT NOT NULL,
                    jd_raw TEXT NOT NULL,
                    saved_at TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    PRIMARY KEY (user_id, record_id),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                """
            )

    @staticmethod
    def _validate_credentials(username: str, password: str) -> tuple[str, str]:
        clean_username = username.strip()
        if not re.fullmatch(r"[\w.\-\u4e00-\u9fff]{2,32}", clean_username):
            raise ValueError("用户名需为 2-32 位，只能包含中英文、数字、下划线、点或短横线。")
        if len(password) < 8:
            raise ValueError("密码至少需要 8 位。")
        return clean_username, password

    @staticmethod
    def _password_digest(password: str, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)

    def register_user(self, username: str, password: str) -> dict:
        clean_username, clean_password = self._validate_credentials(username, password)
        salt = secrets.token_bytes(16)
        digest = self._password_digest(clean_password, salt)
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    "INSERT INTO users (username, password_salt, password_hash) VALUES (?, ?, ?)",
                    (clean_username, base64.urlsafe_b64encode(salt).decode(), base64.urlsafe_b64encode(digest).decode()),
                )
                user_id = cursor.lastrowid
        except sqlite3.IntegrityError as error:
            raise ValueError("这个用户名已经注册，请直接登录或更换用户名。") from error
        return {"id": int(user_id), "username": clean_username}

    def authenticate(self, username: str, password: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, username, password_salt, password_hash FROM users WHERE username = ?",
                (username.strip(),),
            ).fetchone()
        if row is None:
            return None
        salt = base64.urlsafe_b64decode(row["password_salt"])
        expected = base64.urlsafe_b64decode(row["password_hash"])
        actual = self._password_digest(password, salt)
        if not hmac.compare_digest(actual, expected):
            return None
        return {"id": int(row["id"]), "username": row["username"]}

    def ensure_test_user(self) -> dict:
        with self._connect() as connection:
            row = connection.execute("SELECT id, username FROM users WHERE username = ?", ("__app_test__",)).fetchone()
        if row is not None:
            return {"id": int(row["id"]), "username": row["username"]}
        return self.register_user("__app_test__", "app-test-password")

    def _fernet(self) -> Fernet:
        environment_key = os.getenv("AI_RADAR_ENCRYPTION_KEY", "").strip()
        if environment_key:
            return Fernet(environment_key.encode())
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.key_path.exists():
            key = Fernet.generate_key()
            try:
                with self.key_path.open("xb") as handle:
                    handle.write(key)
                try:
                    os.chmod(self.key_path, 0o600)
                except OSError:
                    pass
            except FileExistsError:
                pass
        return Fernet(self.key_path.read_bytes().strip())

    def _encrypt(self, value: str) -> str:
        return self._fernet().encrypt(value.encode("utf-8")).decode() if value else ""

    def _decrypt(self, value: str) -> str:
        if not value:
            return ""
        try:
            return self._fernet().decrypt(value.encode()).decode("utf-8")
        except InvalidToken as error:
            raise RuntimeError("无法解密已保存的 API Key，请重新配置。") from error

    def save_state(self, user_id: int, state: dict) -> None:
        serializable = dict(state)
        api_key = str(serializable.pop("api_key", ""))
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO user_state (user_id, state_json, api_key_encrypted, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    state_json = excluded.state_json,
                    api_key_encrypted = excluded.api_key_encrypted,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user_id, json.dumps(serializable, ensure_ascii=False), self._encrypt(api_key)),
            )

    def load_state(self, user_id: int) -> dict:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT state_json, api_key_encrypted FROM user_state WHERE user_id = ?", (user_id,)
            ).fetchone()
        if row is None:
            return {}
        state = json.loads(row["state_json"])
        state["api_key"] = self._decrypt(row["api_key_encrypted"])
        return state

    def upsert_job(self, user_id: int, record: dict) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO jobs (user_id, record_id, jd_raw, saved_at, snapshot_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, record_id) DO UPDATE SET
                    jd_raw = excluded.jd_raw,
                    saved_at = excluded.saved_at,
                    snapshot_json = excluded.snapshot_json
                """,
                (
                    user_id, record["record_id"], record["jd_raw"], record["saved_at"],
                    json.dumps(record.get("snapshot", {}), ensure_ascii=False),
                ),
            )

    def list_jobs(self, user_id: int) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT record_id, jd_raw, saved_at, snapshot_json FROM jobs WHERE user_id = ? ORDER BY saved_at DESC",
                (user_id,),
            ).fetchall()
        return [
            {
                "record_id": row["record_id"],
                "platform": "用户粘贴",
                "saved_at": row["saved_at"],
                "jd_raw": row["jd_raw"],
                "snapshot": json.loads(row["snapshot_json"]),
            }
            for row in rows
        ]

    def delete_job(self, user_id: int, record_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM jobs WHERE user_id = ? AND record_id = ?", (user_id, record_id))

    def replace_jobs(self, user_id: int, records: list[dict]) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM jobs WHERE user_id = ?", (user_id,))
        for record in records:
            self.upsert_job(user_id, record)
