"""
MyAI Authentication & Session Security Engine
Provides local user authentication, PBKDF2 password hashing, and session management.
Uses built-in Python hashlib and secrets modules without requiring heavyweight external dependencies.
"""

import sqlite3
import hashlib
import secrets
import time
from pathlib import Path
from typing import Optional, Dict, Any

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "myai.db"

# Session validity: 7 days
SESSION_EXPIRATION_SECONDS = 7 * 24 * 3600


def init_auth_tables():
    """Initialize users and active sessions tables."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at INTEGER NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)


init_auth_tables()


def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    """Hash password using PBKDF2-HMAC-SHA256 with random cryptographic salt."""
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations=100_000
    ).hex()
    return hashed, salt


def register_user(username: str, password: str) -> Dict[str, Any]:
    """Register a new user account."""
    clean_username = username.strip().lower()
    if len(clean_username) < 3:
        return {"success": False, "error": "Username must be at least 3 characters."}
    if len(password) < 6:
        return {"success": False, "error": "Password must be at least 6 characters."}

    password_hash, salt = hash_password(password)

    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, password_hash, salt) VALUES (?, ?, ?)",
                (clean_username, password_hash, salt)
            )
            user_id = cursor.lastrowid
            return {"success": True, "user_id": user_id, "username": clean_username}
    except sqlite3.IntegrityError:
        return {"success": False, "error": f"Username '{clean_username}' is already taken."}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def authenticate_user(username: str, password: str) -> Dict[str, Any]:
    """Verify credentials and issue a session token."""
    clean_username = username.strip().lower()

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, username, password_hash, salt FROM users WHERE username = ?",
            (clean_username,)
        )
        row = cursor.fetchone()

    if not row:
        return {"success": False, "error": "Invalid username or password."}

    user_id, uname, stored_hash, salt = row
    computed_hash, _ = hash_password(password, salt)

    if not secrets.compare_digest(stored_hash, computed_hash):
        return {"success": False, "error": "Invalid username or password."}

    # Generate session token
    token = secrets.token_hex(32)
    expires_at = int(time.time()) + SESSION_EXPIRATION_SECONDS

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, user_id, expires_at)
        )

    return {
        "success": True,
        "token": token,
        "username": uname,
        "user_id": user_id,
        "expires_at": expires_at
    }


def validate_session(token: Optional[str]) -> Optional[Dict[str, Any]]:
    """Validate session token and return user details if valid."""
    if not token:
        return None

    now = int(time.time())
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT s.token, u.id, u.username, s.expires_at
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.token = ? AND s.expires_at > ?
            """,
            (token, now)
        )
        row = cursor.fetchone()

    if row:
        return {
            "token": row[0],
            "user_id": row[1],
            "username": row[2],
            "expires_at": row[3]
        }
    return None


def invalidate_session(token: str) -> bool:
    """Log out by deleting the session token."""
    if not token:
        return False
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
        return cursor.rowcount > 0
