"""
MyAI Authentication & Candidate Directory Security Engine
Provides local multi-tenant candidate authentication, PBKDF2 password hashing,
session tokens, and automatic Excel directory synchronization.
"""

import sqlite3
import hashlib
import secrets
import time
from pathlib import Path
from typing import Optional, Dict, Any

from backend.excel_manager import sync_candidates_to_excel

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "myai.db"

# Session validity: 7 days
SESSION_EXPIRATION_SECONDS = 7 * 24 * 3600


def init_auth_tables():
    """Initialize users and active sessions tables with non-destructive migrations."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                full_name TEXT,
                email TEXT,
                phone TEXT,
                role TEXT DEFAULT 'Candidate',
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login_at TIMESTAMP
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

        # Add any missing columns non-destructively
        cursor.execute("PRAGMA table_info(users)")
        cols = [c[1] for c in cursor.fetchall()]
        if "full_name" not in cols:
            cursor.execute("ALTER TABLE users ADD COLUMN full_name TEXT")
        if "email" not in cols:
            cursor.execute("ALTER TABLE users ADD COLUMN email TEXT")
        if "phone" not in cols:
            cursor.execute("ALTER TABLE users ADD COLUMN phone TEXT")
        if "role" not in cols:
            cursor.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'Candidate'")
        if "last_login_at" not in cols:
            cursor.execute("ALTER TABLE users ADD COLUMN last_login_at TIMESTAMP")

        # Ensure default user exists for backward compatibility
        cursor.execute("SELECT id FROM users WHERE id = 1")
        if not cursor.fetchone():
            default_hash, default_salt = hash_password("myai1234")
            cursor.execute("""
                INSERT INTO users (id, username, full_name, email, phone, role, password_hash, salt, last_login_at)
                VALUES (1, 'default', 'Primary User', 'user@myai.local', 'N/A', 'Developer', ?, ?, CURRENT_TIMESTAMP)
            """, (default_hash, default_salt))

    # Initialize Excel directory
    try:
        sync_candidates_to_excel()
    except Exception as exc:
        print(f"[Auth] Initial Excel sync notice: {exc}")


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


def register_user(
    username: str,
    password: str,
    full_name: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    role: Optional[str] = None
) -> Dict[str, Any]:
    """Register a new candidate account and auto-update the Excel roster."""
    clean_username = username.strip().lower()
    clean_fullname = (full_name or clean_username).strip()
    clean_email = (email or "").strip().lower() or None
    clean_phone = (phone or "").strip() or None
    clean_role = (role or "Candidate").strip()

    if len(clean_username) < 3:
        return {"success": False, "error": "Username must be at least 3 characters."}
    if len(password) < 6:
        return {"success": False, "error": "Password must be at least 6 characters."}

    password_hash, salt = hash_password(password)

    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO users (username, full_name, email, phone, role, password_hash, salt, last_login_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (clean_username, clean_fullname, clean_email, clean_phone, clean_role, password_hash, salt)
            )
            user_id = cursor.lastrowid

            # Generate initial active session token
            token = secrets.token_hex(32)
            expires_at = int(time.time()) + SESSION_EXPIRATION_SECONDS
            cursor.execute(
                "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
                (token, user_id, expires_at)
            )

        # Automatically update candidate details in Excel
        sync_candidates_to_excel()

        return {
            "success": True,
            "user_id": user_id,
            "username": clean_username,
            "full_name": clean_fullname,
            "email": clean_email,
            "phone": clean_phone,
            "role": clean_role,
            "token": token,
            "expires_at": expires_at
        }
    except sqlite3.IntegrityError:
        return {"success": False, "error": f"Username '{clean_username}' is already taken."}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def authenticate_user(username_or_email: str, password: str) -> Dict[str, Any]:
    """Verify credentials and issue a session token; updates Excel last-login timestamp."""
    identifier = username_or_email.strip().lower()

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, username, full_name, email, phone, role, password_hash, salt
            FROM users
            WHERE username = ? OR email = ?
            """,
            (identifier, identifier)
        )
        row = cursor.fetchone()

    if not row:
        return {"success": False, "error": "Invalid username or password."}

    user_id, uname, fname, email, phone, role, stored_hash, salt = row
    computed_hash, _ = hash_password(password, salt)

    if not secrets.compare_digest(stored_hash, computed_hash):
        return {"success": False, "error": "Invalid username or password."}

    # Generate session token
    token = secrets.token_hex(32)
    expires_at = int(time.time()) + SESSION_EXPIRATION_SECONDS

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, user_id, expires_at)
        )
        cursor.execute(
            "UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = ?",
            (user_id,)
        )

    # Auto-update Excel with new activity
    try:
        sync_candidates_to_excel()
    except Exception:
        pass

    return {
        "success": True,
        "token": token,
        "user_id": user_id,
        "username": uname,
        "full_name": fname or uname,
        "email": email,
        "phone": phone,
        "role": role or "Candidate",
        "expires_at": expires_at
    }


def validate_session(token: Optional[str]) -> Optional[Dict[str, Any]]:
    """Validate session token and return complete user profile if valid."""
    if not token:
        return None

    now = int(time.time())
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT s.token, u.id, u.username, u.full_name, u.email, u.phone, u.role, s.expires_at
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
            "full_name": row[3] or row[2],
            "email": row[4],
            "phone": row[5],
            "role": row[6] or "Candidate",
            "expires_at": row[7]
        }
    return None


def invalidate_session(token: str) -> bool:
    """Log out candidate by terminating the session token."""
    if not token:
        return False
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
        return cursor.rowcount > 0


init_auth_tables()
