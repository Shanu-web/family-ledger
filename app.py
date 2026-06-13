"""
Family Ledger — backend (MVP v1)
FastAPI + SQLite. Event-logged mutations, confirm-before-commit drafts,
phone+OTP auth (dev mode), family workspace with roles & invites.

Run:  uvicorn app:app --reload --host 0.0.0.0 --port 8000
Dev OTP: printed to console (and returned in response when DEV_MODE=1).
Optional: set ANTHROPIC_API_KEY to enable AI extraction (text + documents).
"""
import os, json, sqlite3, secrets, hashlib, time, re, base64
from datetime import datetime, timedelta
from contextlib import contextmanager
from typing import Optional

import httpx
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from webauthn import (generate_registration_options, verify_registration_response,
                      generate_authentication_options, verify_authentication_response, options_to_json)
from webauthn.helpers import bytes_to_base64url, base64url_to_bytes
from webauthn.helpers.structs import (PublicKeyCredentialDescriptor,
                                      AuthenticatorSelectionCriteria, ResidentKeyRequirement,
                                      UserVerificationRequirement)
from fastapi import FastAPI, Request, HTTPException, Depends, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

# Load .env from the app folder if present (no dependency needed).
_ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_ENV_FILE):
    with open(_ENV_FILE) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

# If a persistent volume is mounted at /data (Railway), use it automatically —
# otherwise data lives next to the app (local dev) and is wiped on each redeploy.
_DATA_DIR = "/data" if (os.path.isdir("/data") and os.access("/data", os.W_OK)) else "."
DB_PATH = os.environ.get("FL_DB", os.path.join(_DATA_DIR, "family.db"))
VAULT_DIR = os.environ.get("FL_VAULT", os.path.join(_DATA_DIR, "vault"))
DEV_MODE = os.environ.get("DEV_MODE", "1") == "1"
# .strip() guards against a trailing newline/space pasted into the host's
# env var UI (e.g. Railway) — a present-but-invalid key is the most common
# cause of "key is set but extraction says it isn't".
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
MODEL = os.environ.get("FL_MODEL", "claude-sonnet-4-6").strip()
# Optional server-side speech-to-text (Sarvam) — far more accurate for Hindi/Hinglish
# than the browser's built-in recognition. Without a key, the browser engine is used.
SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY", "").strip()
SARVAM_MODEL = os.environ.get("FL_STT_MODEL", "saarika:v2.5").strip()
# Default to auto-detect so a family can speak ANY supported language. A per-capture
# override (from the UI) can pin a specific language when auto-detect struggles.
SARVAM_LANG = os.environ.get("FL_STT_LANG", "unknown").strip()
STT_LANGS = {"unknown", "hi-IN", "en-IN", "bn-IN", "kn-IN", "ml-IN", "mr-IN",
             "od-IN", "pa-IN", "ta-IN", "te-IN", "gu-IN"}
print(f"[boot] AI extraction {'ENABLED' if ANTHROPIC_API_KEY else 'DISABLED (ANTHROPIC_API_KEY not set)'}; model={MODEL}")
print(f"[boot] Sarvam STT {'ENABLED' if SARVAM_API_KEY else 'DISABLED (browser speech only)'}; model={SARVAM_MODEL}, lang={SARVAM_LANG}")

os.makedirs(VAULT_DIR, exist_ok=True)
app = FastAPI(title="Family Ledger")

# ───────────────────────── database ─────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS families(
  id TEXT PRIMARY KEY, name TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS persons(
  id TEXT PRIMARY KEY, family_id TEXT, name TEXT, relation TEXT,
  status TEXT DEFAULT 'alive', phone TEXT, pan_last4 TEXT, notes TEXT,
  birth_year TEXT, death_year TEXT, story TEXT,
  added_by TEXT, deleted_at TEXT,
  FOREIGN KEY(family_id) REFERENCES families(id));
CREATE TABLE IF NOT EXISTS users(
  id TEXT PRIMARY KEY, phone TEXT UNIQUE, person_id TEXT, family_id TEXT,
  role TEXT DEFAULT 'member', created_at TEXT);
CREATE TABLE IF NOT EXISTS sessions(
  token TEXT PRIMARY KEY, user_id TEXT, created_at TEXT, expires_at TEXT);
CREATE TABLE IF NOT EXISTS otps(
  phone TEXT PRIMARY KEY, code TEXT, expires_at TEXT, attempts INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS verified_phones(
  vtoken TEXT PRIMARY KEY, phone TEXT, expires_at TEXT);
CREATE TABLE IF NOT EXISTS invites(
  code TEXT PRIMARY KEY, family_id TEXT, phone TEXT, role TEXT,
  person_id TEXT, created_by TEXT, expires_at TEXT, used_at TEXT);
CREATE TABLE IF NOT EXISTS assets(
  id TEXT PRIMARY KEY, family_id TEXT, owner_person_id TEXT, kind TEXT,
  category TEXT, title TEXT, details TEXT, doc_location TEXT,
  nominee TEXT DEFAULT 'unknown', mutation TEXT DEFAULT 'unknown',
  status TEXT DEFAULT 'pending', amount REAL, linked_asset_id TEXT,
  extra TEXT, added_by TEXT, deleted_at TEXT);
CREATE TABLE IF NOT EXISTS checks(
  id TEXT, family_id TEXT, done INTEGER DEFAULT 0, note TEXT, by_user TEXT,
  PRIMARY KEY(id, family_id));
CREATE TABLE IF NOT EXISTS drafts(
  id TEXT PRIMARY KEY, family_id TEXT, source TEXT, payload TEXT,
  confidence REAL, created_by TEXT, created_at TEXT, status TEXT DEFAULT 'open');
CREATE TABLE IF NOT EXISTS documents(
  id TEXT PRIMARY KEY, family_id TEXT, filename TEXT, sha256 TEXT,
  doc_type TEXT, linked_asset_id TEXT, uploaded_by TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY AUTOINCREMENT, family_id TEXT, actor TEXT,
  type TEXT, payload TEXT, client_key TEXT UNIQUE, created_at TEXT);
-- Vault encryption (Option B: per-family passphrase, envelope-wrapped DEK).
-- We store ONLY wrapped keys + ciphertext at rest; the passphrase and the
-- plaintext data-encryption-key (DEK) are never persisted. The DEK is wrapped
-- twice — once by the passphrase, once by a one-time recovery code — so a lost
-- passphrase can be recovered, but losing BOTH means the data is unrecoverable.
CREATE TABLE IF NOT EXISTS vault_keys(
  family_id TEXT PRIMARY KEY,
  salt_pass BLOB, nonce_pass BLOB, dek_pass BLOB,
  salt_rec BLOB, nonce_rec BLOB, dek_rec BLOB,
  created_at TEXT, rotated_at TEXT);
CREATE TABLE IF NOT EXISTS succession_cases(
  id TEXT PRIMARY KEY, family_id TEXT, person_id TEXT, status TEXT DEFAULT 'open',
  note TEXT, opened_by TEXT, opened_at TEXT, closed_at TEXT, deleted_at TEXT);
CREATE TABLE IF NOT EXISTS succession_tasks(
  id TEXT PRIMARY KEY, case_id TEXT, family_id TEXT, asset_id TEXT,
  category TEXT, title TEXT, kind TEXT, claimant_person_id TEXT,
  status TEXT DEFAULT 'not_started', docs TEXT, note TEXT,
  updated_by TEXT, updated_at TEXT);
-- Passkeys (WebAuthn): device-based login, no SMS. Each credential stores the
-- authenticator's PUBLIC key only; the private key never leaves the user's device.
CREATE TABLE IF NOT EXISTS credentials(
  id TEXT PRIMARY KEY, user_id TEXT, family_id TEXT,
  public_key BLOB, sign_count INTEGER DEFAULT 0,
  device_label TEXT, created_at TEXT, last_used_at TEXT);
-- Short-lived server state binding a WebAuthn challenge to a login attempt.
CREATE TABLE IF NOT EXISTS webauthn_flows(
  handle TEXT PRIMARY KEY, phone TEXT, kind TEXT, challenge TEXT,
  action TEXT, user_id TEXT, rp_id TEXT, origin TEXT, expires_at TEXT);
"""

@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")     # safe concurrent reads/writes
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

with db() as c:
    c.executescript(SCHEMA)
    for _mig in ("ALTER TABLE assets ADD COLUMN extra TEXT",
                 "ALTER TABLE persons ADD COLUMN birth_year TEXT",
                 "ALTER TABLE persons ADD COLUMN death_year TEXT",
                 "ALTER TABLE persons ADD COLUMN story TEXT",
                 "ALTER TABLE documents ADD COLUMN encrypted INTEGER DEFAULT 0"):
        try:  # migrate pre-existing DBs
            c.execute(_mig)
        except sqlite3.OperationalError:
            pass

def now() -> str:
    return datetime.utcnow().isoformat()

def nid() -> str:
    return secrets.token_hex(8)

def seen_key(conn, client_key) -> bool:
    """True if this idempotency key was already processed — caller should skip the write."""
    if not client_key:
        return False
    return conn.execute("SELECT id FROM events WHERE client_key=?", (client_key,)).fetchone() is not None

def emit(conn, family_id, actor, etype, payload, client_key=None):
    """Append-only event log. Idempotent on client_key."""
    if client_key:
        dup = conn.execute("SELECT id FROM events WHERE client_key=?", (client_key,)).fetchone()
        if dup:
            return False
    conn.execute(
        "INSERT INTO events(family_id, actor, type, payload, client_key, created_at) VALUES(?,?,?,?,?,?)",
        (family_id, actor, etype, json.dumps(payload, ensure_ascii=False), client_key, now()),
    )
    return True

# ───────────────────────── vault crypto (Option B) ─────────────────────────
# Envelope encryption: a random 256-bit data key (DEK) encrypts every vault
# file with AES-256-GCM. The DEK itself is wrapped (encrypted) by two key-
# encryption-keys (KEKs): one derived from the family passphrase, one from a
# one-time recovery code. At rest we keep only wrapped keys + ciphertext, so the
# server cannot read documents on its own. An unlocked DEK lives only in process
# memory, keyed by session token, and expires — never touching disk.

VAULT_UNLOCK_TTL = 30 * 60          # an unlocked vault re-locks after 30 min idle
_VAULT_UNLOCKED: dict = {}          # session_token -> {"dek": bytes, "expires": float}

def _kdf(passphrase: str, salt: bytes) -> bytes:
    """Slow, memory-hard key derivation (scrypt) — resists brute force."""
    return hashlib.scrypt(passphrase.encode("utf-8"), salt=salt,
                          n=2**14, r=8, p=1, dklen=32, maxmem=64 * 1024 * 1024)

def _wrap(dek: bytes, kek: bytes):
    nonce = secrets.token_bytes(12)
    return nonce, AESGCM(kek).encrypt(nonce, dek, None)

def _unwrap(nonce: bytes, ct: bytes, kek: bytes) -> bytes:
    return AESGCM(kek).decrypt(nonce, ct, None)   # raises on wrong key / tampering

def _enc_blob(dek: bytes, data: bytes) -> bytes:
    nonce = secrets.token_bytes(12)
    return nonce + AESGCM(dek).encrypt(nonce, data, None)

def _dec_blob(dek: bytes, blob: bytes) -> bytes:
    return AESGCM(dek).decrypt(blob[:12], blob[12:], None)

def _fmt_recovery(raw: str) -> str:
    """20 hex chars -> FAMILY-XXXXX-XXXXX-XXXXX-XXXXX (shown once)."""
    s = raw.upper()
    return "FAMILY-" + "-".join(s[i:i + 5] for i in range(0, 20, 5))

def _norm_recovery(code: str) -> str:
    # strip the human-readable "FAMILY" label first (its letters f/a are valid hex)
    code = re.sub(r"(?i)family", "", code or "")
    return re.sub(r"[^a-f0-9]", "", code.lower())

def vault_unlock_mem(token: str, dek: bytes):
    _VAULT_UNLOCKED[token] = {"dek": dek, "expires": time.time() + VAULT_UNLOCK_TTL}

def vault_dek(token: str) -> Optional[bytes]:
    """Return the in-memory DEK for this session, or None if locked/expired."""
    ent = _VAULT_UNLOCKED.get(token)
    if not ent:
        return None
    if ent["expires"] < time.time():
        _VAULT_UNLOCKED.pop(token, None)
        return None
    ent["expires"] = time.time() + VAULT_UNLOCK_TTL   # sliding expiry on use
    return ent["dek"]

# ───────────────────────── auth helpers ─────────────────────────

def user_from_token(token: str):
    if not token:
        raise HTTPException(401, "Not signed in")
    with db() as c:
        s = c.execute("SELECT * FROM sessions WHERE token=?", (token,)).fetchone()
        if not s or s["expires_at"] < now():
            raise HTTPException(401, "Session expired")
        u = c.execute("SELECT * FROM users WHERE id=?", (s["user_id"],)).fetchone()
        if not u:
            raise HTTPException(401, "User not found")
        p = c.execute("SELECT name FROM persons WHERE id=?", (u["person_id"],)).fetchone()
        return {"id": u["id"], "phone": u["phone"], "person_id": u["person_id"],
                "family_id": u["family_id"], "role": u["role"], "token": token,
                "name": p["name"] if p else u["phone"]}

def get_user(request: Request):
    return user_from_token(request.headers.get("authorization", "").replace("Bearer ", ""))

def require_writer(user):
    if user["role"] == "viewer":
        raise HTTPException(403, "Viewers cannot make changes")

def person_in_family(conn, pid, family_id) -> bool:
    return bool(pid) and conn.execute(
        "SELECT 1 FROM persons WHERE id=? AND family_id=? AND deleted_at IS NULL",
        (pid, family_id)).fetchone() is not None

def make_session(conn, user_id):
    token = secrets.token_hex(24)
    conn.execute("INSERT INTO sessions(token, user_id, created_at, expires_at) VALUES(?,?,?,?)",
                 (token, user_id, now(), (datetime.utcnow() + timedelta(days=30)).isoformat()))
    return token

# ───────────────────────── auth flow (W1) ─────────────────────────

class PhoneIn(BaseModel):
    phone: str

class VerifyIn(BaseModel):
    phone: str
    otp: str

class CompleteIn(BaseModel):
    vtoken: str
    action: str                      # login | register | join_invite | claim
    name: Optional[str] = None
    family_name: Optional[str] = None
    person_id: Optional[str] = None  # for claim

def norm_phone(p: str) -> str:
    return re.sub(r"\D", "", p)[-10:]

@app.post("/api/auth/request-otp")
def request_otp(body: PhoneIn):
    phone = norm_phone(body.phone)
    if len(phone) != 10:
        raise HTTPException(400, "Enter a valid 10-digit phone number")
    code = "123456" if DEV_MODE else f"{secrets.randbelow(1000000):06d}"
    with db() as c:
        c.execute("REPLACE INTO otps(phone, code, expires_at, attempts) VALUES(?,?,?,0)",
                  (phone, code, (datetime.utcnow() + timedelta(minutes=10)).isoformat()))
    print(f"[OTP] {phone} -> {code}")
    # Never reveal whether the phone is registered before OTP verification.
    return {"sent": True, **({"dev_otp": code} if DEV_MODE else {})}

@app.post("/api/auth/verify")
def verify_otp(body: VerifyIn):
    phone = norm_phone(body.phone)
    with db() as c:
        row = c.execute("SELECT * FROM otps WHERE phone=?", (phone,)).fetchone()
        if not row or row["expires_at"] < now():
            raise HTTPException(400, "OTP expired — request a new one")
        if row["attempts"] >= 5:
            raise HTTPException(429, "Too many attempts — wait 30 minutes")
        if row["code"] != body.otp.strip():
            c.execute("UPDATE otps SET attempts=attempts+1 WHERE phone=?", (phone,))
            c.commit()  # commit before raising — HTTPException would otherwise skip commit and defeat rate limiting
            raise HTTPException(400, "Incorrect OTP")
        c.execute("DELETE FROM otps WHERE phone=?", (phone,))
        vtoken = secrets.token_hex(16)
        c.execute("INSERT INTO verified_phones(vtoken, phone, expires_at) VALUES(?,?,?)",
                  (vtoken, phone, (datetime.utcnow() + timedelta(minutes=15)).isoformat()))

        # Branch resolution, in priority order (spec W1).
        user = c.execute("SELECT * FROM users WHERE phone=?", (phone,)).fetchone()
        if user:
            token = make_session(c, user["id"])
            return {"next": "session", "token": token}

        inv = c.execute(
            "SELECT * FROM invites WHERE phone=? AND used_at IS NULL AND expires_at>?",
            (phone, now())).fetchone()
        if inv:
            fam = c.execute("SELECT name FROM families WHERE id=?", (inv["family_id"],)).fetchone()
            return {"next": "join_invite", "vtoken": vtoken,
                    "family_name": fam["name"] if fam else "your family", "role": inv["role"]}

        claim = c.execute(
            "SELECT p.id, p.name, p.relation, f.name AS family_name FROM persons p "
            "JOIN families f ON f.id=p.family_id "
            "WHERE p.phone=? AND p.deleted_at IS NULL "
            "AND p.id NOT IN (SELECT person_id FROM users WHERE person_id IS NOT NULL)",
            (phone,)).fetchall()
        if claim:
            return {"next": "claim", "vtoken": vtoken,
                    "candidates": [dict(r) for r in claim]}

        return {"next": "register", "vtoken": vtoken}

@app.post("/api/auth/complete")
def complete_auth(body: CompleteIn):
    with db() as c:
        v = c.execute("SELECT * FROM verified_phones WHERE vtoken=?", (body.vtoken,)).fetchone()
        if not v or v["expires_at"] < now():
            raise HTTPException(400, "Verification expired — start again")
        phone = v["phone"]
        c.execute("DELETE FROM verified_phones WHERE vtoken=?", (body.vtoken,))

        if body.action == "register":
            if not body.name:
                raise HTTPException(400, "Name is required")
            fam_id, person_id, user_id = nid(), nid(), nid()
            c.execute("INSERT INTO families(id, name, created_at) VALUES(?,?,?)",
                      (fam_id, body.family_name or f"{body.name.split()[0]} family", now()))
            c.execute("INSERT INTO persons(id, family_id, name, relation, phone, added_by) VALUES(?,?,?,?,?,?)",
                      (person_id, fam_id, body.name.strip(), "Self", phone, body.name.strip()))
            c.execute("INSERT INTO users(id, phone, person_id, family_id, role, created_at) VALUES(?,?,?,?,?,?)",
                      (user_id, phone, person_id, fam_id, "owner", now()))
            emit(c, fam_id, body.name.strip(), "family.created", {"family": body.family_name or ""})
            return {"token": make_session(c, user_id)}

        if body.action == "join_invite":
            inv = c.execute(
                "SELECT * FROM invites WHERE phone=? AND used_at IS NULL AND expires_at>?",
                (phone, now())).fetchone()
            if not inv:
                raise HTTPException(400, "Invite not found or expired")
            person_id = inv["person_id"]
            if person_id:
                pname = c.execute("SELECT name FROM persons WHERE id=?", (person_id,)).fetchone()["name"]
            else:
                if not body.name:
                    raise HTTPException(400, "Name is required")
                person_id, pname = nid(), body.name.strip()
                c.execute("INSERT INTO persons(id, family_id, name, relation, phone, added_by) VALUES(?,?,?,?,?,?)",
                          (person_id, inv["family_id"], pname, "Other", phone, pname))
            user_id = nid()
            c.execute("INSERT INTO users(id, phone, person_id, family_id, role, created_at) VALUES(?,?,?,?,?,?)",
                      (user_id, phone, person_id, inv["family_id"], inv["role"], now()))
            c.execute("UPDATE invites SET used_at=? WHERE code=?", (now(), inv["code"]))
            emit(c, inv["family_id"], pname, "member.joined", {"role": inv["role"]})
            return {"token": make_session(c, user_id)}

        if body.action == "claim":
            p = c.execute(
                "SELECT * FROM persons WHERE id=? AND phone=? AND deleted_at IS NULL",
                (body.person_id, phone)).fetchone()
            if not p:
                raise HTTPException(400, "Profile not found")
            user_id = nid()
            c.execute("INSERT INTO users(id, phone, person_id, family_id, role, created_at) VALUES(?,?,?,?,?,?)",
                      (user_id, phone, p["id"], p["family_id"], "member", now()))
            emit(c, p["family_id"], p["name"], "profile.claimed",
                 {"person": p["name"], "note": "existing profile linked to new login"})
            return {"token": make_session(c, user_id)}

        raise HTTPException(400, "Unknown action")

# ───────────────────────── auth: passkeys / WebAuthn (no SMS) ─────────────────────────
# Device-based login. Trust for a NEW person comes from the family owner's invite
# (or a claimable profile), not from an SMS to the phone. The owner who creates a
# family self-enrolls the first device. Returning users sign in with the device
# biometric. Phone number still anchors identity (invites/claims key off it).

RP_NAME = "Family Ledger"
WEBAUTHN_TTL = 5 * 60

def rp_info(request: Request):
    """RP ID + origin must match what the browser sees. Overridable for deploys."""
    host = request.headers.get("host", "localhost:8000")
    rp_id = os.environ.get("FL_RP_ID", "").strip() or host.split(":")[0]
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme or "http"
    origin = os.environ.get("FL_ORIGIN", "").strip() or f"{proto}://{host}"
    return rp_id, origin

def claim_candidates(c, phone):
    return c.execute(
        "SELECT p.id, p.name, p.relation, f.name AS family_name FROM persons p "
        "JOIN families f ON f.id=p.family_id "
        "WHERE p.phone=? AND p.deleted_at IS NULL "
        "AND p.id NOT IN (SELECT person_id FROM users WHERE person_id IS NOT NULL)",
        (phone,)).fetchall()

def _store_flow(c, handle, phone, kind, challenge, action, user_id, rp_id, origin):
    c.execute("REPLACE INTO webauthn_flows(handle, phone, kind, challenge, action, user_id, rp_id, origin, expires_at)"
              " VALUES(?,?,?,?,?,?,?,?,?)",
              (handle, phone, kind, bytes_to_base64url(challenge), action, user_id, rp_id, origin,
               (datetime.utcnow() + timedelta(seconds=WEBAUTHN_TTL)).isoformat()))

def _reg_options(c, request, phone, action, user_id, exclude_ids=()):
    rp_id, origin = rp_info(request)
    opts = generate_registration_options(
        rp_id=rp_id, rp_name=RP_NAME, user_id=user_id.encode(), user_name=phone,
        user_display_name=phone,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED),
        exclude_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(i)) for i in exclude_ids])
    handle = nid()
    _store_flow(c, handle, phone, "register", opts.challenge, action, user_id, rp_id, origin)
    return handle, json.loads(options_to_json(opts))

@app.post("/api/auth/passkey/begin")
def passkey_begin(body: PhoneIn, request: Request):
    phone = norm_phone(body.phone)
    if len(phone) != 10:
        raise HTTPException(400, "Enter a valid 10-digit phone number")
    rp_id, origin = rp_info(request)
    with db() as c:
        user = c.execute("SELECT * FROM users WHERE phone=?", (phone,)).fetchone()
        creds = c.execute("SELECT id FROM credentials WHERE user_id=?",
                          (user["id"],)).fetchall() if user else []
        invite = c.execute(
            "SELECT * FROM invites WHERE phone=? AND used_at IS NULL AND expires_at>?",
            (phone, now())).fetchone()

        # Returning user with a registered device → authenticate (biometric).
        if user and creds:
            opts = generate_authentication_options(
                rp_id=rp_id,
                allow_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(r["id"])) for r in creds],
                user_verification=UserVerificationRequirement.PREFERRED)
            handle = nid()
            _store_flow(c, handle, phone, "authenticate", opts.challenge, "login", user["id"], rp_id, origin)
            return {"mode": "authenticate", "handle": handle,
                    "options": json.loads(options_to_json(opts)),
                    "can_add_device": bool(invite)}

        # No usable device → enrol one (registration), if trust allows.
        if user and invite:                      # owner re-vouched → add a device to existing user
            handle, options = _reg_options(c, request, phone, "add_device", user["id"])
            return {"mode": "register", "next": "add_device", "handle": handle, "options": options}
        if user and not invite:                  # existing account, no device, no vouch
            return {"mode": "blocked", "reason": "no_device",
                    "message": "This number has an account but no device set up here. "
                               "Ask the family owner to re-invite your number to add this device."}
        if invite:                               # owner invited a new person
            fam = c.execute("SELECT name FROM families WHERE id=?", (invite["family_id"],)).fetchone()
            handle, options = _reg_options(c, request, phone, "join_invite", nid())
            return {"mode": "register", "next": "join_invite", "handle": handle, "options": options,
                    "family_name": fam["name"] if fam else "your family", "role": invite["role"],
                    "need_name": invite["person_id"] is None}
        cands = claim_candidates(c, phone)       # an existing profile to claim
        if cands:
            handle, options = _reg_options(c, request, phone, "claim", nid())
            return {"mode": "register", "next": "claim", "handle": handle, "options": options,
                    "candidates": [dict(r) for r in cands]}
        # brand-new number with no invite → start your own family (you become owner)
        handle, options = _reg_options(c, request, phone, "register", nid())
        return {"mode": "register", "next": "register", "handle": handle, "options": options}

@app.post("/api/auth/passkey/add-begin")
def passkey_add_begin(body: PhoneIn, request: Request):
    """Enrol a NEW device for an existing account — requires a fresh owner invite."""
    phone = norm_phone(body.phone)
    with db() as c:
        user = c.execute("SELECT * FROM users WHERE phone=?", (phone,)).fetchone()
        invite = c.execute(
            "SELECT * FROM invites WHERE phone=? AND used_at IS NULL AND expires_at>?",
            (phone, now())).fetchone()
        if not (user and invite):
            raise HTTPException(400, "Ask the family owner to re-invite your number, then try again")
        exclude = [r["id"] for r in c.execute("SELECT id FROM credentials WHERE user_id=?", (user["id"],))]
        handle, options = _reg_options(c, request, phone, "add_device", user["id"], exclude)
    return {"mode": "register", "next": "add_device", "handle": handle, "options": options}

class PasskeyComplete(BaseModel):
    handle: str
    credential: dict
    action: Optional[str] = None          # UI may pick a sub-action (e.g. claim vs new family)
    name: Optional[str] = None
    family_name: Optional[str] = None
    person_id: Optional[str] = None
    device_label: Optional[str] = None

@app.post("/api/auth/passkey/complete")
def passkey_complete(body: PasskeyComplete):
    with db() as c:
        flow = c.execute("SELECT * FROM webauthn_flows WHERE handle=?", (body.handle,)).fetchone()
        if not flow or flow["expires_at"] < now():
            raise HTTPException(400, "Login attempt expired — start again")
        c.execute("DELETE FROM webauthn_flows WHERE handle=?", (body.handle,))
        challenge = base64url_to_bytes(flow["challenge"])
        rp_id, origin = flow["rp_id"], flow["origin"]

        # ── authenticate ──
        if flow["kind"] == "authenticate":
            cred_id = body.credential.get("id") or body.credential.get("rawId")
            row = c.execute("SELECT * FROM credentials WHERE id=?", (cred_id,)).fetchone()
            if not row:
                raise HTTPException(400, "Unknown device")
            try:
                res = verify_authentication_response(
                    credential=json.dumps(body.credential), expected_challenge=challenge,
                    expected_rp_id=rp_id, expected_origin=origin,
                    credential_public_key=row["public_key"], credential_current_sign_count=row["sign_count"])
            except Exception:
                raise HTTPException(400, "Passkey verification failed")
            c.execute("UPDATE credentials SET sign_count=?, last_used_at=? WHERE id=?",
                      (res.new_sign_count, now(), cred_id))
            return {"token": make_session(c, row["user_id"])}

        # ── register (enrol a device + perform the account action) ──
        try:
            reg = verify_registration_response(
                credential=json.dumps(body.credential), expected_challenge=challenge,
                expected_rp_id=rp_id, expected_origin=origin)
        except Exception:
            raise HTTPException(400, "Could not register this device")
        cred_id = bytes_to_base64url(reg.credential_id)
        phone = flow["phone"]
        action = body.action or flow["action"]
        label = (body.device_label or "This device")[:40]

        def save_cred(uid, fid):
            c.execute("INSERT OR REPLACE INTO credentials(id, user_id, family_id, public_key, sign_count,"
                      " device_label, created_at, last_used_at) VALUES(?,?,?,?,?,?,?,?)",
                      (cred_id, uid, fid, reg.credential_public_key, reg.sign_count, label, now(), now()))

        if action == "register":
            if c.execute("SELECT 1 FROM users WHERE phone=?", (phone,)).fetchone():
                raise HTTPException(400, "This number already has an account")
            if not body.name:
                raise HTTPException(400, "Name is required")
            fam_id, person_id, user_id = nid(), nid(), flow["user_id"]
            c.execute("INSERT INTO families(id, name, created_at) VALUES(?,?,?)",
                      (fam_id, body.family_name or f"{body.name.split()[0]} family", now()))
            c.execute("INSERT INTO persons(id, family_id, name, relation, phone, added_by) VALUES(?,?,?,?,?,?)",
                      (person_id, fam_id, body.name.strip(), "Self", phone, body.name.strip()))
            c.execute("INSERT INTO users(id, phone, person_id, family_id, role, created_at) VALUES(?,?,?,?,?,?)",
                      (user_id, phone, person_id, fam_id, "owner", now()))
            save_cred(user_id, fam_id)
            emit(c, fam_id, body.name.strip(), "family.created", {"family": body.family_name or ""})
            return {"token": make_session(c, user_id)}

        if action == "join_invite":
            inv = c.execute("SELECT * FROM invites WHERE phone=? AND used_at IS NULL AND expires_at>?",
                            (phone, now())).fetchone()
            if not inv:
                raise HTTPException(400, "Invite not found or expired")
            if inv["person_id"]:
                person_id = inv["person_id"]
                pname = c.execute("SELECT name FROM persons WHERE id=?", (person_id,)).fetchone()["name"]
            else:
                if not body.name:
                    raise HTTPException(400, "Name is required")
                person_id, pname = nid(), body.name.strip()
                c.execute("INSERT INTO persons(id, family_id, name, relation, phone, added_by) VALUES(?,?,?,?,?,?)",
                          (person_id, inv["family_id"], pname, "Other", phone, pname))
            user_id = flow["user_id"]
            c.execute("INSERT INTO users(id, phone, person_id, family_id, role, created_at) VALUES(?,?,?,?,?,?)",
                      (user_id, phone, person_id, inv["family_id"], inv["role"], now()))
            c.execute("UPDATE invites SET used_at=? WHERE code=?", (now(), inv["code"]))
            save_cred(user_id, inv["family_id"])
            emit(c, inv["family_id"], pname, "member.joined", {"role": inv["role"]})
            return {"token": make_session(c, user_id)}

        if action == "claim":
            p = c.execute("SELECT * FROM persons WHERE id=? AND phone=? AND deleted_at IS NULL",
                          (body.person_id, phone)).fetchone()
            if not p:
                raise HTTPException(400, "Profile not found")
            user_id = flow["user_id"]
            c.execute("INSERT INTO users(id, phone, person_id, family_id, role, created_at) VALUES(?,?,?,?,?,?)",
                      (user_id, phone, p["id"], p["family_id"], "member", now()))
            save_cred(user_id, p["family_id"])
            emit(c, p["family_id"], p["name"], "profile.claimed",
                 {"person": p["name"], "note": "existing profile linked via passkey"})
            return {"token": make_session(c, user_id)}

        if action == "add_device":
            inv = c.execute("SELECT * FROM invites WHERE phone=? AND used_at IS NULL AND expires_at>?",
                            (phone, now())).fetchone()
            user = c.execute("SELECT * FROM users WHERE phone=?", (phone,)).fetchone()
            if not (user and inv):
                raise HTTPException(400, "Adding a device needs a fresh owner invite")
            c.execute("UPDATE invites SET used_at=? WHERE code=?", (now(), inv["code"]))
            save_cred(user["id"], user["family_id"])
            emit(c, user["family_id"], user["phone"], "device.added", {})
            return {"token": make_session(c, user["id"])}

        raise HTTPException(400, "Unknown action")

# ───────────────────────── registered devices ─────────────────────────

@app.get("/api/credentials")
def list_credentials(user=Depends(get_user)):
    with db() as c:
        rows = [dict(r) for r in c.execute(
            "SELECT id, device_label, created_at, last_used_at FROM credentials WHERE user_id=? ORDER BY rowid",
            (user["id"],))]
    return {"devices": rows}

class DeviceLabelIn(BaseModel):
    device_label: str

@app.patch("/api/credentials/{cred_id}")
def rename_credential(cred_id: str, body: DeviceLabelIn, user=Depends(get_user)):
    with db() as c:
        c.execute("UPDATE credentials SET device_label=? WHERE id=? AND user_id=?",
                  (body.device_label[:40], cred_id, user["id"]))
    return {"ok": True}

@app.delete("/api/credentials/{cred_id}")
def remove_credential(cred_id: str, user=Depends(get_user)):
    with db() as c:
        n = c.execute("SELECT COUNT(*) n FROM credentials WHERE user_id=?", (user["id"],)).fetchone()["n"]
        if n <= 1:
            raise HTTPException(400, "You can't remove your only device — add another first")
        c.execute("DELETE FROM credentials WHERE id=? AND user_id=?", (cred_id, user["id"]))
        emit(c, user["family_id"], user["name"], "device.removed", {})
    return {"ok": True}

@app.get("/api/config")
def config():
    return {"dev_mode": DEV_MODE, "stt": bool(SARVAM_API_KEY)}

@app.get("/api/me")
def me(user=Depends(get_user)):
    with db() as c:
        fam = c.execute("SELECT name FROM families WHERE id=?", (user["family_id"],)).fetchone()
    return {**user, "family_name": fam["name"] if fam else ""}

# ───────────────────────── document vault (encryption at rest) ─────────────────────────

class VaultSetupIn(BaseModel):
    passphrase: str

class VaultUnlockIn(BaseModel):
    passphrase: str

class VaultRecoverIn(BaseModel):
    recovery_code: str
    new_passphrase: str

class VaultChangeIn(BaseModel):
    old_passphrase: str
    new_passphrase: str

def _vault_row(c, family_id):
    return c.execute("SELECT * FROM vault_keys WHERE family_id=?", (family_id,)).fetchone()

@app.get("/api/vault/status")
def vault_status(user=Depends(get_user)):
    with db() as c:
        row = _vault_row(c, user["family_id"])
        ndocs = c.execute("SELECT COUNT(*) n FROM documents WHERE family_id=?",
                          (user["family_id"],)).fetchone()["n"]
    return {"configured": bool(row), "unlocked": vault_dek(user["token"]) is not None,
            "documents": ndocs}

@app.post("/api/vault/setup")
def vault_setup(body: VaultSetupIn, user=Depends(get_user)):
    if user["role"] != "owner":
        raise HTTPException(403, "Only the family owner can set up the vault")
    if len(body.passphrase or "") < 6:
        raise HTTPException(400, "Passphrase must be at least 6 characters")
    with db() as c:
        if _vault_row(c, user["family_id"]):
            raise HTTPException(400, "Vault is already set up")
        dek = secrets.token_bytes(32)
        recovery_raw = secrets.token_hex(10)                 # 20 hex chars, shown once
        salt_p, salt_r = secrets.token_bytes(16), secrets.token_bytes(16)
        np, cp = _wrap(dek, _kdf(body.passphrase, salt_p))
        nr, cr = _wrap(dek, _kdf(_norm_recovery(recovery_raw), salt_r))
        c.execute("INSERT INTO vault_keys(family_id, salt_pass, nonce_pass, dek_pass,"
                  " salt_rec, nonce_rec, dek_rec, created_at) VALUES(?,?,?,?,?,?,?,?)",
                  (user["family_id"], salt_p, np, cp, salt_r, nr, cr, now()))
        emit(c, user["family_id"], user["name"], "vault.created", {})
    vault_unlock_mem(user["token"], dek)
    return {"ok": True, "recovery_code": _fmt_recovery(recovery_raw),
            "note": "Save this recovery code somewhere safe. It is shown only once and is "
                    "the ONLY way back in if the passphrase is forgotten."}

@app.post("/api/vault/unlock")
def vault_unlock(body: VaultUnlockIn, user=Depends(get_user)):
    with db() as c:
        row = _vault_row(c, user["family_id"])
        if not row:
            raise HTTPException(400, "Vault is not set up yet")
    try:
        dek = _unwrap(row["nonce_pass"], row["dek_pass"], _kdf(body.passphrase, row["salt_pass"]))
    except Exception:
        raise HTTPException(400, "Incorrect passphrase")
    vault_unlock_mem(user["token"], dek)
    return {"ok": True}

@app.post("/api/vault/lock")
def vault_lock(user=Depends(get_user)):
    _VAULT_UNLOCKED.pop(user["token"], None)
    return {"ok": True}

@app.post("/api/vault/recover")
def vault_recover(body: VaultRecoverIn, user=Depends(get_user)):
    if user["role"] != "owner":
        raise HTTPException(403, "Only the family owner can reset the passphrase")
    if len(body.new_passphrase or "") < 6:
        raise HTTPException(400, "New passphrase must be at least 6 characters")
    with db() as c:
        row = _vault_row(c, user["family_id"])
        if not row:
            raise HTTPException(400, "Vault is not set up yet")
        try:
            dek = _unwrap(row["nonce_rec"], row["dek_rec"],
                          _kdf(_norm_recovery(body.recovery_code), row["salt_rec"]))
        except Exception:
            raise HTTPException(400, "Incorrect recovery code")
        salt_p, (np, cp) = secrets.token_bytes(16), (None, None)
        np, cp = _wrap(dek, _kdf(body.new_passphrase, salt_p))
        c.execute("UPDATE vault_keys SET salt_pass=?, nonce_pass=?, dek_pass=?, rotated_at=? WHERE family_id=?",
                  (salt_p, np, cp, now(), user["family_id"]))
        emit(c, user["family_id"], user["name"], "vault.recovered", {})
    vault_unlock_mem(user["token"], dek)
    return {"ok": True, "note": "Passphrase reset using your recovery code. The vault is unlocked."}

@app.post("/api/vault/change-passphrase")
def vault_change(body: VaultChangeIn, user=Depends(get_user)):
    if user["role"] != "owner":
        raise HTTPException(403, "Only the family owner can change the passphrase")
    if len(body.new_passphrase or "") < 6:
        raise HTTPException(400, "New passphrase must be at least 6 characters")
    with db() as c:
        row = _vault_row(c, user["family_id"])
        if not row:
            raise HTTPException(400, "Vault is not set up yet")
        try:
            dek = _unwrap(row["nonce_pass"], row["dek_pass"], _kdf(body.old_passphrase, row["salt_pass"]))
        except Exception:
            raise HTTPException(400, "Current passphrase is incorrect")
        salt_p = secrets.token_bytes(16)
        np, cp = _wrap(dek, _kdf(body.new_passphrase, salt_p))
        c.execute("UPDATE vault_keys SET salt_pass=?, nonce_pass=?, dek_pass=?, rotated_at=? WHERE family_id=?",
                  (salt_p, np, cp, now(), user["family_id"]))
        emit(c, user["family_id"], user["name"], "vault.passphrase_changed", {})
    vault_unlock_mem(user["token"], dek)
    return {"ok": True}

@app.get("/api/documents")
def list_documents(user=Depends(get_user)):
    with db() as c:
        rows = [dict(r) for r in c.execute(
            "SELECT id, filename, doc_type, linked_asset_id, uploaded_by, created_at, encrypted"
            " FROM documents WHERE family_id=? ORDER BY rowid DESC", (user["family_id"],))]
    return {"documents": rows, "unlocked": vault_dek(user["token"]) is not None}

@app.get("/api/documents/{doc_id}/file")
def get_document(doc_id: str, t: str):
    user = user_from_token(t)
    dek = vault_dek(user["token"])
    if dek is None:
        raise HTTPException(409, "Vault is locked — unlock it to view documents")
    with db() as c:
        d = c.execute("SELECT * FROM documents WHERE id=? AND family_id=?",
                      (doc_id, user["family_id"])).fetchone()
    if not d:
        raise HTTPException(404, "Document not found")
    ext = os.path.splitext(d["filename"] or "doc.jpg")[1] or ".jpg"
    path = os.path.join(VAULT_DIR, d["sha256"] + (".enc" if d["encrypted"] else ext))
    if not os.path.exists(path):
        raise HTTPException(404, "File missing from vault")
    raw = open(path, "rb").read()
    if d["encrypted"]:
        try:
            raw = _dec_blob(dek, raw)
        except Exception:
            raise HTTPException(500, "Could not decrypt — wrong key state")
    media = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
             ".pdf": "application/pdf", ".webp": "image/webp"}.get(ext.lower(), "application/octet-stream")
    from fastapi.responses import Response
    return Response(content=raw, media_type=media,
                    headers={"Content-Disposition": f'inline; filename="{d["filename"] or "document"}"'})

# ───────────────────────── family & members ─────────────────────────

class MemberIn(BaseModel):
    name: str
    relation: str = "Other"
    status: str = "alive"
    phone: Optional[str] = None
    pan_last4: Optional[str] = None
    notes: Optional[str] = None
    birth_year: Optional[str] = None
    death_year: Optional[str] = None
    story: Optional[str] = None      # life story / memories for future generations

@app.get("/api/family")
def family(user=Depends(get_user)):
    with db() as c:
        members = [dict(r) for r in c.execute(
            "SELECT * FROM persons WHERE family_id=? AND deleted_at IS NULL ORDER BY rowid",
            (user["family_id"],))]
        events = [dict(r) for r in c.execute(
            "SELECT actor, type, payload, created_at FROM events WHERE family_id=? ORDER BY id DESC LIMIT 15",
            (user["family_id"],))]
        invites = [dict(r) for r in c.execute(
            "SELECT code, phone, role, expires_at FROM invites WHERE family_id=? AND used_at IS NULL AND expires_at>?",
            (user["family_id"], now()))]
    return {"members": members, "activity": events, "invites": invites}

@app.post("/api/members")
def add_member(m: MemberIn, request: Request, user=Depends(get_user)):
    require_writer(user)
    pid = nid()
    with db() as c:
        if seen_key(c, request.headers.get("idempotency-key")):
            return {"id": None, "duplicate": True}
        c.execute(
            "INSERT INTO persons(id, family_id, name, relation, status, phone, pan_last4, notes,"
            " birth_year, death_year, story, added_by) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (pid, user["family_id"], m.name.strip(), m.relation, m.status,
             norm_phone(m.phone) if m.phone else None, (m.pan_last4 or "")[:4], m.notes,
             m.birth_year, m.death_year, m.story, user["name"]))
        emit(c, user["family_id"], user["name"], "member.added", {"name": m.name},
             request.headers.get("idempotency-key"))
    return {"id": pid}

@app.patch("/api/members/{pid}")
def edit_member(pid: str, m: MemberIn, user=Depends(get_user)):
    require_writer(user)
    with db() as c:
        c.execute(
            "UPDATE persons SET name=?, relation=?, status=?, phone=?, pan_last4=?, notes=?,"
            " birth_year=?, death_year=?, story=? WHERE id=? AND family_id=?",
            (m.name.strip(), m.relation, m.status, norm_phone(m.phone) if m.phone else None,
             (m.pan_last4 or "")[:4], m.notes, m.birth_year, m.death_year, m.story,
             pid, user["family_id"]))
        emit(c, user["family_id"], user["name"], "member.updated", {"name": m.name})
    return {"ok": True}

@app.delete("/api/members/{pid}")
def delete_member(pid: str, user=Depends(get_user)):
    require_writer(user)
    with db() as c:
        p = c.execute("SELECT name, id FROM persons WHERE id=? AND family_id=?",
                      (pid, user["family_id"])).fetchone()
        if not p:
            raise HTTPException(404, "Not found")
        if pid == user["person_id"]:
            raise HTTPException(400, "You cannot remove your own profile")
        c.execute("UPDATE persons SET deleted_at=? WHERE id=?", (now(), pid))   # soft delete
        c.execute("UPDATE assets SET deleted_at=? WHERE owner_person_id=? AND family_id=?",
                  (now(), pid, user["family_id"]))
        emit(c, user["family_id"], user["name"], "member.removed", {"name": p["name"]})
    return {"ok": True}

class InviteIn(BaseModel):
    phone: str
    role: str = "member"
    person_id: Optional[str] = None

@app.post("/api/invites")
def create_invite(inv: InviteIn, user=Depends(get_user)):
    if user["role"] != "owner":
        raise HTTPException(403, "Only the owner can invite")
    if inv.role not in ("member", "viewer"):
        raise HTTPException(400, "Role must be member or viewer")
    code = secrets.token_hex(4)
    with db() as c:
        c.execute(
            "INSERT INTO invites(code, family_id, phone, role, person_id, created_by, expires_at) VALUES(?,?,?,?,?,?,?)",
            (code, user["family_id"], norm_phone(inv.phone), inv.role, inv.person_id,
             user["id"], (datetime.utcnow() + timedelta(days=7)).isoformat()))
        emit(c, user["family_id"], user["name"], "invite.sent",
             {"phone": "••••" + norm_phone(inv.phone)[-4:], "role": inv.role})
    return {"code": code, "note": "Invitee signs in with this phone number; the invite is matched automatically."}

# ───────────────────────── assets & flags ─────────────────────────

CATEGORIES = ["property", "bank", "insurance", "epf", "demat", "gold", "vehicle", "loan"]
FINANCIAL = {"bank", "insurance", "epf", "demat"}

def flags_for(a: dict):
    f = []
    if a["kind"] == "asset":
        if a["category"] in FINANCIAL and a["nominee"] != "yes":
            f.append("Nominee missing or unknown")
        if a["category"] == "property" and a["mutation"] != "done":
            f.append("Mutation pending")
        if not (a["doc_location"] or "").strip():
            f.append("Document location not recorded")
    return f

class AssetIn(BaseModel):
    kind: str = "asset"               # asset | liability
    category: str
    title: str
    owner_person_id: str
    details: Optional[str] = None
    doc_location: Optional[str] = None
    nominee: str = "unknown"
    mutation: str = "unknown"
    status: str = "pending"
    amount: Optional[float] = None
    linked_asset_id: Optional[str] = None
    extra: Optional[dict] = None     # category-specific structured fields (lender, EMI, khata, insurer…)

@app.get("/api/assets")
def list_assets(user=Depends(get_user)):
    with db() as c:
        rows = [dict(r) for r in c.execute(
            "SELECT * FROM assets WHERE family_id=? AND deleted_at IS NULL ORDER BY rowid",
            (user["family_id"],))]
    for r in rows:
        r["flags"] = flags_for(r)
        r["extra"] = json.loads(r["extra"]) if r.get("extra") else {}
    return {"assets": rows}

@app.post("/api/assets")
def add_asset(a: AssetIn, request: Request, user=Depends(get_user)):
    require_writer(user)
    if a.category not in CATEGORIES:
        raise HTTPException(400, "Unknown category")
    if a.kind not in ("asset", "liability"):
        raise HTTPException(400, "kind must be asset or liability")
    aid = nid()
    with db() as c:
        if not person_in_family(c, a.owner_person_id, user["family_id"]):
            raise HTTPException(400, "Owner must be a member of your family")
        if seen_key(c, request.headers.get("idempotency-key")):
            return {"id": None, "duplicate": True}
        c.execute(
            "INSERT INTO assets(id, family_id, owner_person_id, kind, category, title, details, doc_location,"
            " nominee, mutation, status, amount, linked_asset_id, extra, added_by)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (aid, user["family_id"], a.owner_person_id, a.kind, a.category, a.title.strip(), a.details,
             a.doc_location, a.nominee, a.mutation, a.status, a.amount, a.linked_asset_id,
             json.dumps(a.extra, ensure_ascii=False) if a.extra else None, user["name"]))
        emit(c, user["family_id"], user["name"],
             "liability.added" if a.kind == "liability" else "asset.added",
             {"title": a.title}, request.headers.get("idempotency-key"))
    return {"id": aid}

@app.patch("/api/assets/{aid}")
def edit_asset(aid: str, a: AssetIn, user=Depends(get_user)):
    require_writer(user)
    if a.category not in CATEGORIES:
        raise HTTPException(400, "Unknown category")
    with db() as c:
        if not person_in_family(c, a.owner_person_id, user["family_id"]):
            raise HTTPException(400, "Owner must be a member of your family")
        c.execute(
            "UPDATE assets SET owner_person_id=?, kind=?, category=?, title=?, details=?, doc_location=?,"
            " nominee=?, mutation=?, status=?, amount=?, linked_asset_id=?, extra=? WHERE id=? AND family_id=?",
            (a.owner_person_id, a.kind, a.category, a.title.strip(), a.details, a.doc_location,
             a.nominee, a.mutation, a.status, a.amount, a.linked_asset_id,
             json.dumps(a.extra, ensure_ascii=False) if a.extra else None, aid, user["family_id"]))
        emit(c, user["family_id"], user["name"], "asset.updated", {"title": a.title})
    return {"ok": True}

@app.delete("/api/assets/{aid}")
def delete_asset(aid: str, user=Depends(get_user)):
    require_writer(user)
    with db() as c:
        a = c.execute("SELECT title FROM assets WHERE id=? AND family_id=?", (aid, user["family_id"])).fetchone()
        if not a:
            raise HTTPException(404, "Not found")
        c.execute("UPDATE assets SET deleted_at=? WHERE id=?", (now(), aid))
        emit(c, user["family_id"], user["name"], "asset.deleted", {"title": a["title"]})
    return {"ok": True}

# ───────────────────────── discovery checks ─────────────────────────

class CheckIn(BaseModel):
    id: str
    done: Optional[bool] = None
    note: Optional[str] = None

@app.get("/api/checks")
def get_checks(user=Depends(get_user)):
    with db() as c:
        rows = {r["id"]: dict(r) for r in c.execute(
            "SELECT * FROM checks WHERE family_id=?", (user["family_id"],))}
    return {"checks": rows}

@app.post("/api/checks")
def set_check(ck: CheckIn, user=Depends(get_user)):
    require_writer(user)
    with db() as c:
        row = c.execute("SELECT * FROM checks WHERE id=? AND family_id=?",
                        (ck.id, user["family_id"])).fetchone()
        done = (1 if ck.done else 0) if ck.done is not None else (row["done"] if row else 0)
        note = ck.note if ck.note is not None else (row["note"] if row else "")
        c.execute("REPLACE INTO checks(id, family_id, done, note, by_user) VALUES(?,?,?,?,?)",
                  (ck.id, user["family_id"], done, note, user["name"]))
        if ck.done is not None:
            emit(c, user["family_id"], user["name"],
                 "check.done" if ck.done else "check.reopened", {"check": ck.id})
    return {"ok": True}

# ───────────────────────── ingestion: drafts (W2/W3) ─────────────────────────

EXTRACT_PROMPT = """You extract structured records from a family conversation transcript for an Indian family asset register. The transcript may be in ANY Indian language (Hindi, Hinglish, English, Tamil, Telugu, Kannada, Malayalam, Marathi, Bengali, Gujarati, Punjabi, Odia, or code-mixed). Understand whatever language is used; keep names/titles in the words spoken. Return ONLY a JSON array, no prose, no markdown fences. Each element:
{"entity":"person|asset|liability","confidence":0.0-1.0,
 "name":"(person only)","relation":"Self|Spouse|Father|Mother|Son|Daughter|Brother|Sister|Grandfather|Grandmother|Other","status":"alive|deceased",
 "birth_year":"(person, if said)","death_year":"(person, if said)","story":"(person) any life details told about them — kahan rehte the, kya karte the, kaisi shakhsiyat — preserve the storyteller's words",
 "category":"property|bank|insurance|epf|demat|gold|vehicle|loan (asset/liability only)",
 "title":"short asset/liability name","owner_hint":"name or relation of owner if mentioned",
 "details":"anything said that doesn't fit a field below — never full sensitive numbers","amount":number or null,
 "doc_location":"where papers are kept, if mentioned","nominee":"yes|no|unknown","mutation":"done|pending|unknown",
 "extra":{category-specific structured fields, include ONLY what is actually said:
   property: ptype(flat/house/plot/agricultural land), location, khata_khesra, area, registry_year, papers_with(self/bank/relative — original papers held where)
   bank: bank, branch, acc_type(savings/current/FD/RD), account_last4, maturity
   insurance: insurer, policy_type(term/endowment/ULIP/health/vehicle), policy_last4, sum_assured, premium, premium_freq, maturity
   epf: scheme(EPF/PPF/NPS/Sukanya), employer, uan_last4
   demat: broker_amc, folio_last4, sip_amount, sip_since, expected_return
   gold: form(jewellery/coins/bars/SGB), weight_gms, storage(home/bank locker — which bank, branch)
   vehicle: make_model, reg_no, insurance_expiry
   loan: lender, loan_type(home/personal/gold/vehicle/education), sanctioned, emi, tenure_years, started, account_last4}}
For loans: "amount" = current OUTSTANDING balance; the sanctioned amount goes in extra.sanctioned; EMI in extra.emi.
Rules: extract ONLY what is actually said — never invent values. If a number/name is unclear, omit it and lower confidence. Multiple entities per transcript are expected. Deceased relatives mentioned with assets are persons too.

Amount rules (critical — spoken transcripts have no punctuation, segment carefully):
- Convert Indian units: X lakh = X*100000, X crore = X*10000000.
- Each spoken amount belongs to EXACTLY ONE entity. Never copy the same amount to multiple entities. If unsure which entity an amount belongs to, set amount null and mention it in details.
- An amount stated immediately after an asset is usually that asset's value, and the NEXT amount usually belongs to the NEXT entity. "ghar hai karib 80 lakh ka, loan hai, 27 lakh" → house value 80 lakh, loan 27 lakh (the trailing amount binds to the loan).
- EMI / kist / premium / SIP is a RECURRING payment, never the total value. EMI → extra.emi, premium → extra.premium, SIP → extra.sip_amount. "SIP 65000 per month" means amount stays null unless the current holding value is also stated; if they say since when (e.g. "2021 se"), put it in extra.sip_since.

Example. Transcript: "gaon me zameen hai karib 50 lakh ki loan chal raha hai 12 lakh emi 30000 aur gaadi ka insurance v hai"
Output: [
 {"entity":"asset","category":"property","title":"Zameen (village)","amount":5000000,"confidence":0.85,"nominee":"unknown","mutation":"unknown"},
 {"entity":"liability","category":"loan","title":"Loan","amount":1200000,"details":"EMI 30000/month","confidence":0.85,"nominee":"unknown","mutation":"unknown"},
 {"entity":"asset","category":"insurance","title":"Vehicle insurance","amount":null,"confidence":0.8,"nominee":"unknown","mutation":"unknown"}]"""

def claude_extract(text: str, image_b64: Optional[str] = None, media_type: str = "image/jpeg"):
    """Returns the extracted list on success, or None on failure.
    On failure, the reason is stored in claude_extract.last_error so callers
    can tell 'no key' apart from 'API call failed'."""
    claude_extract.last_error = None
    if not ANTHROPIC_API_KEY:
        claude_extract.last_error = "no_key"
        return None
    content = []
    if image_b64:
        content.append({"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}})
        content.append({"type": "text", "text": "Extract records from this Indian family document (deed/policy/passbook/RC). Mask any full Aadhaar/PAN/account numbers to last 4 digits. " + EXTRACT_PROMPT})
    else:
        content.append({"type": "text", "text": EXTRACT_PROMPT + "\n\nTranscript:\n" + text})
    try:
        r = httpx.post("https://api.anthropic.com/v1/messages",
                       headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01",
                                "content-type": "application/json"},
                       json={"model": MODEL, "max_tokens": 1500,
                             "messages": [{"role": "user", "content": content}]},
                       timeout=60)
        r.raise_for_status()
        out = "".join(b.get("text", "") for b in r.json()["content"] if b.get("type") == "text")
        out = re.sub(r"```json|```", "", out).strip()
        return json.loads(out)
    except httpx.HTTPStatusError as e:
        detail = e.response.text[:300] if e.response is not None else str(e)
        claude_extract.last_error = f"HTTP {e.response.status_code if e.response is not None else '?'}: {detail}"
        print("[extract] Claude API returned an error:", claude_extract.last_error)
        return None
    except Exception as e:
        claude_extract.last_error = f"{type(e).__name__}: {e}"
        print("[extract] Claude call failed:", claude_extract.last_error)
        return None

claude_extract.last_error = None

LAKH = r"(\d+(?:\.\d+)?)\s*(lakh|lac|लाख|crore|करोड़|cr)"

def fallback_extract(text: str):
    """No API key: honest keyword-level parser. Low confidence by design.
    Each amount is assigned to the NEAREST category keyword (max 60 chars away),
    and each amount is used at most once — so '80 lakh ka ghar, 27 lakh loan'
    doesn't stamp 80L on everything."""
    t = text.lower()
    amounts = []   # [{pos, value}]
    for m in re.finditer(LAKH, t):
        n = float(m.group(1))
        amounts.append({"pos": m.start(),
                        "value": n * (10000000 if m.group(2) in ("crore", "करोड़", "cr") else 100000)})
    pairs = [("property", ["ghar", "makaan", "makan", "zameen", "jameen", "plot", "flat", "house", "land", "khet"]),
             ("bank", ["fd", "fixed deposit", "bank", "saving", "rd", "khata"]),
             ("insurance", ["lic", "bima", "policy", "insurance", "term"]),
             ("epf", ["pf", "epf", "ppf", "nps", "pension"]),
             ("demat", ["share", "mutual fund", "demat", "stock", "sip"]),
             ("gold", ["gold", "sona", "locker", "jewel"]),
             ("vehicle", ["car", "gaadi", "gadi", "bike", "scooty", "vehicle"]),
             ("loan", ["loan", "karz", "karza", "udhaar", "udhar", "emi", "credit card"])]
    cats = []      # [(category, [keyword positions])]
    for cat, kws in pairs:
        pos = [m.start() for kw in kws for m in re.finditer(re.escape(kw), t)]
        if pos:
            cats.append((cat, pos))
    # greedy nearest-first assignment: each category gets at most one amount, each amount used once
    cand = sorted((min(abs(a["pos"] - p) for p in ps), ci, ai)
                  for ci, (_, ps) in enumerate(cats) for ai, a in enumerate(amounts))
    assigned, used = {}, set()
    for d, ci, ai in cand:
        if d > 60 or ci in assigned or ai in used:
            continue
        assigned[ci] = amounts[ai]["value"]
        used.add(ai)
    return [{"entity": "liability" if cat == "loan" else "asset", "category": cat,
             "title": cat.capitalize() + " (from conversation)", "confidence": 0.4,
             "details": text[:240], "amount": assigned.get(ci),
             "nominee": "unknown", "mutation": "unknown"}
            for ci, (cat, _) in enumerate(cats)]

class IngestText(BaseModel):
    transcript: str

@app.post("/api/ingest/text")
def ingest_text(body: IngestText, user=Depends(get_user)):
    require_writer(user)
    text = body.transcript.strip()
    if not text:
        raise HTTPException(400, "Empty transcript")
    if len(text) > 20000:
        raise HTTPException(400, "Transcript too long")
    items = claude_extract(text)
    engine = "claude"
    if items is None:
        items = fallback_extract(text)
        engine = "fallback"
    created = []
    with db() as c:
        for it in items if isinstance(items, list) else []:
            did = nid()
            c.execute("INSERT INTO drafts(id, family_id, source, payload, confidence, created_by, created_at)"
                      " VALUES(?,?,?,?,?,?,?)",
                      (did, user["family_id"], f"voice/{engine}", json.dumps(it, ensure_ascii=False),
                       float(it.get("confidence", 0.5) or 0.5), user["name"], now()))
            created.append({"id": did, **it})
        emit(c, user["family_id"], user["name"], "ingest.text",
             {"chars": len(text), "drafts": len(created), "engine": engine})
    note = None
    if engine != "claude":
        note = ("AI key not configured — basic keyword extraction used. Review drafts carefully."
                if claude_extract.last_error == "no_key" else
                "AI extraction failed (key is set but the call errored) — basic keyword "
                "extraction used. Check server logs. Review drafts carefully.")
    return {"drafts": created, "engine": engine, "note": note}

@app.post("/api/stt")
async def speech_to_text(file: UploadFile = File(...), user_token: str = Form(...),
                         language_code: str = Form(None)):
    """Server-side STT via Sarvam (Saarika). Audio never persists — transcribed in memory.
    The transcript is returned to the client for review; it does NOT auto-write anything.
    language_code defaults to auto-detect, so the speaker can use any supported language."""
    user = user_from_token(user_token)
    require_writer(user)
    if not SARVAM_API_KEY:
        raise HTTPException(400, "Server-side transcription isn't configured (SARVAM_API_KEY not set)")
    lang = language_code if language_code in STT_LANGS else SARVAM_LANG
    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty audio")
    if len(data) > 12_000_000:
        raise HTTPException(400, "Audio too large — keep clips under ~30 seconds")
    try:
        r = httpx.post(
            "https://api.sarvam.ai/speech-to-text",
            headers={"api-subscription-key": SARVAM_API_KEY},
            data={"model": SARVAM_MODEL, "language_code": lang},
            files={"file": (file.filename or "audio.webm", data, file.content_type or "audio/webm")},
            timeout=60)
        r.raise_for_status()
        j = r.json()
    except httpx.HTTPStatusError as e:
        detail = e.response.text[:200] if e.response is not None else str(e)
        code = e.response.status_code if e.response is not None else "?"
        # 30s limit on the sync API is the most common cause of a 4xx here
        raise HTTPException(502, f"Transcription failed (Sarvam {code}). {detail}")
    except Exception as e:
        raise HTTPException(502, f"Transcription failed: {type(e).__name__}")
    return {"transcript": (j.get("transcript") or "").strip(),
            "language_code": j.get("language_code")}

@app.post("/api/ingest/document")
async def ingest_document(file: UploadFile = File(...), user_token: str = Form(...)):
    # multipart can't easily carry the auth header from fetch FormData in some setups; accept token in form
    user = user_from_token(user_token)
    require_writer(user)
    # Vault must be set up and unlocked — documents are only ever stored encrypted.
    with db() as c:
        if not _vault_row(c, user["family_id"]):
            raise HTTPException(400, "Set up your document vault (passphrase) before uploading documents")
    dek = vault_dek(user["token"])
    if dek is None:
        raise HTTPException(409, "Vault is locked — unlock it to upload documents")
    data = await file.read()
    if len(data) > 8_000_000:
        raise HTTPException(400, "File too large (max 8 MB)")
    sha = hashlib.sha256(data).hexdigest()   # hash of plaintext → content dedupe
    with db() as c:
        dup = c.execute("SELECT id FROM documents WHERE sha256=? AND family_id=?",
                        (sha, user["family_id"])).fetchone()
        if dup:
            return {"duplicate": True, "note": "This document is already in the vault."}
    media = file.content_type or "image/jpeg"
    items = None
    if media.startswith("image/"):
        items = claude_extract("", base64.b64encode(data).decode(), media)   # extract from plaintext, in memory
    # encrypt before it ever touches disk
    path = os.path.join(VAULT_DIR, sha + ".enc")
    with open(path, "wb") as f:
        f.write(_enc_blob(dek, data))
    doc_id = nid()
    created = []
    with db() as c:
        c.execute("INSERT INTO documents(id, family_id, filename, sha256, doc_type, uploaded_by, created_at, encrypted)"
                  " VALUES(?,?,?,?,?,?,?,1)",
                  (doc_id, user["family_id"], file.filename, sha,
                   (items[0].get("category") if items else "unclassified") or "unclassified",
                   user["name"], now()))
        for it in items or []:
            did = nid()
            it["document_id"] = doc_id
            c.execute("INSERT INTO drafts(id, family_id, source, payload, confidence, created_by, created_at)"
                      " VALUES(?,?,?,?,?,?,?)",
                      (did, user["family_id"], "document", json.dumps(it, ensure_ascii=False),
                       float(it.get("confidence", 0.5) or 0.5), user["name"], now()))
            created.append({"id": did, **it})
        emit(c, user["family_id"], user["name"], "document.uploaded",
             {"file": file.filename, "drafts": len(created)})
    return {"document_id": doc_id, "drafts": created,
            "note": None if items else "Stored in vault. AI extraction unavailable — add details manually."}

@app.get("/api/ai/health")
def ai_health():
    """Unauthenticated diagnostics for deployment (Railway etc.).
    Reports whether the key is visible to the process (masked) and, if so,
    pings the Anthropic API so you can tell 'key missing' from 'key invalid'."""
    key = ANTHROPIC_API_KEY
    out = {
        "key_present": bool(key),
        "key_length": len(key),
        "key_preview": (key[:7] + "…" + key[-4:]) if len(key) > 12 else None,
        "model": MODEL,
    }
    if not key:
        out["status"] = "no_key"
        out["hint"] = "ANTHROPIC_API_KEY is not visible to the app. On Railway: set it on the correct service, then redeploy."
        return out
    try:
        r = httpx.post("https://api.anthropic.com/v1/messages",
                       headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                                "content-type": "application/json"},
                       json={"model": MODEL, "max_tokens": 4,
                             "messages": [{"role": "user", "content": "ping"}]},
                       timeout=30)
        out["status"] = "ok" if r.status_code == 200 else "api_error"
        out["api_status_code"] = r.status_code
        if r.status_code != 200:
            out["api_response"] = r.text[:300]
            out["hint"] = "Key reached Anthropic but was rejected. Check for a wrong/expired key, trailing whitespace, or an unknown model name."
    except Exception as e:
        out["status"] = "unreachable"
        out["error"] = f"{type(e).__name__}: {e}"
    return out

@app.get("/api/drafts")
def list_drafts(user=Depends(get_user)):
    with db() as c:
        rows = [{"id": r["id"], "source": r["source"], "confidence": r["confidence"],
                 "created_by": r["created_by"], **json.loads(r["payload"])}
                for r in c.execute(
                    "SELECT * FROM drafts WHERE family_id=? AND status='open' ORDER BY rowid DESC",
                    (user["family_id"],))]
    return {"drafts": rows}

class ConfirmIn(BaseModel):
    payload: dict   # possibly user-edited before confirm

@app.post("/api/drafts/{did}/confirm")
def confirm_draft(did: str, body: ConfirmIn, request: Request, user=Depends(get_user)):
    require_writer(user)
    p = body.payload
    with db() as c:
        d = c.execute("SELECT * FROM drafts WHERE id=? AND family_id=? AND status='open'",
                      (did, user["family_id"])).fetchone()
        if not d:
            raise HTTPException(404, "Draft not found")
        if seen_key(c, request.headers.get("idempotency-key")):
            c.execute("UPDATE drafts SET status='confirmed' WHERE id=? AND family_id=?", (did, user["family_id"]))
            return {"ok": True, "duplicate": True}
        if p.get("entity") == "person":
            pid = nid()
            c.execute("INSERT INTO persons(id, family_id, name, relation, status, birth_year, death_year, story, added_by)"
                      " VALUES(?,?,?,?,?,?,?,?,?)",
                      (pid, user["family_id"], p.get("name", "Unknown"), p.get("relation", "Other"),
                       p.get("status", "alive"), p.get("birth_year"), p.get("death_year"),
                       p.get("story"), user["name"]))
            emit(c, user["family_id"], user["name"], "member.added",
                 {"name": p.get("name"), "via": "draft"}, request.headers.get("idempotency-key"))
        else:
            owner = p.get("owner_person_id") or user["person_id"]
            if not person_in_family(c, owner, user["family_id"]):
                raise HTTPException(400, "Owner must be a member of your family")
            aid = nid()
            c.execute(
                "INSERT INTO assets(id, family_id, owner_person_id, kind, category, title, details, doc_location,"
                " nominee, mutation, status, amount, extra, added_by) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (aid, user["family_id"], owner,
                 "liability" if p.get("entity") == "liability" else "asset",
                 p.get("category", "bank"), p.get("title", "Untitled"), p.get("details"),
                 p.get("doc_location"), p.get("nominee", "unknown"), p.get("mutation", "unknown"),
                 "pending", p.get("amount"),
                 json.dumps(p.get("extra"), ensure_ascii=False) if p.get("extra") else None, user["name"]))
            if p.get("document_id"):
                c.execute("UPDATE documents SET linked_asset_id=? WHERE id=? AND family_id=?",
                          (aid, p["document_id"], user["family_id"]))
            emit(c, user["family_id"], user["name"], "asset.added",
                 {"title": p.get("title"), "via": "draft"}, request.headers.get("idempotency-key"))
        c.execute("UPDATE drafts SET status='confirmed' WHERE id=? AND family_id=?", (did, user["family_id"]))
    return {"ok": True}

@app.post("/api/drafts/{did}/reject")
def reject_draft(did: str, user=Depends(get_user)):
    require_writer(user)
    with db() as c:
        c.execute("UPDATE drafts SET status='rejected' WHERE id=? AND family_id=?", (did, user["family_id"]))
        emit(c, user["family_id"], user["name"], "draft.rejected", {"id": did})
    return {"ok": True}

# ───────────────────────── succession / transmission (W5) ─────────────────────────
# When a family member dies, every asset they held must be claimed or transferred
# (transmission). India needs different paperwork per institution; this turns the
# register into a per-asset action plan with status tracking. General procedural
# guidance only — not legal advice.

SUCCESSION_STATUSES = ["not_started", "gathering", "filed", "transferred", "blocked", "na"]

SUCCESSION_GUIDANCE = {
    "bank": {
        "label": "Bank accounts & deposits",
        "documents": ["Death certificate (original + several attested copies)",
                      "Claimant/nominee PAN, Aadhaar & KYC", "Account number / passbook",
                      "Bank's death-claim form", "If no nominee & balance is large: succession "
                      "certificate / legal heir certificate, indemnity bond, sureties"],
        "steps": ["Notify the branch and freeze further debits.",
                  "Submit the death-claim form with the death certificate.",
                  "If a nominee is registered, the balance is released to the nominee.",
                  "If no nominee, follow the succession-certificate / legal-heir route."],
        "where": "The account holder's home branch."},
    "insurance": {
        "label": "Life / other insurance",
        "documents": ["Death certificate", "Original policy document", "Claimant ID & bank details",
                      "Insurer's claim/intimation form",
                      "For early or unnatural death: FIR, post-mortem & hospital records"],
        "steps": ["Intimate the insurer as early as possible (delays can complicate claims).",
                  "Submit the claim form with all documents.",
                  "The nominee receives the sum assured; if no nominee, heirs must establish title."],
        "where": "Insurer branch or online claims portal (LIC / SBI Life / HDFC Life etc.)."},
    "epf": {
        "label": "EPF / PPF / NPS / pension",
        "documents": ["Death certificate", "Form 20 (EPF, by nominee/legal heir)",
                      "Form 10D (pension) & Form 5IF (EDLI insurance)", "Nominee KYC & bank details",
                      "For PPF/NPS: scheme-specific death-claim form"],
        "steps": ["For EPF, file through the last employer or online on the EPFO portal.",
                  "Claim provident fund (Form 20), pension (10D) and EDLI (5IF) together.",
                  "PPF/NPS are claimed at the holding bank / NPS CRA."],
        "where": "EPFO (via employer or unified portal) / holding bank / NPS CRA."},
    "property": {
        "label": "Property & land",
        "documents": ["Death certificate", "Will (if any) or legal-heir / succession certificate",
                      "Title deed & prior chain of documents", "Mutation (dakhil-kharij) application",
                      "Latest tax / utility receipts"],
        "steps": ["Establish heirship (will, or legal-heir/succession certificate).",
                  "File for mutation at the local revenue/municipal office to update title records.",
                  "For registered transfer, execute the relevant deed at the sub-registrar.",
                  "Clear any pending property tax or society dues."],
        "where": "Tehsil / municipal office (mutation); sub-registrar (registered transfer)."},
    "demat": {
        "label": "Shares & mutual funds",
        "documents": ["Death certificate", "Transmission Request Form (TRF)",
                      "Claimant KYC & client-master / folio details",
                      "If no nominee & above threshold: succession certificate / probate / LoA"],
        "steps": ["Submit a transmission request to the Depository Participant (broker) for shares.",
                  "For mutual funds, submit the AMC/RTA transmission form per folio.",
                  "Nominee holdings transmit on documents; otherwise heirs must establish title."],
        "where": "Depository Participant (broker) / AMC or RTA (CAMS, KFintech)."},
    "gold": {
        "label": "Gold & locker contents",
        "documents": ["Death certificate", "Locker-holder nominee KYC & locker agreement",
                      "For Sovereign Gold Bonds: transmission request via RBI/depository"],
        "steps": ["For a bank locker, the nominee/heir accesses contents with the bank's witness procedure.",
                  "Physical gold passes per the will / family settlement.",
                  "SGBs are transmitted through the issuing bank / depository."],
        "where": "Bank locker branch / SGB issuer."},
    "vehicle": {
        "label": "Vehicles",
        "documents": ["Death certificate", "Registration Certificate (RC)",
                      "Form 31 (transfer on death of owner)", "Insurance papers", "Legal-heir proof"],
        "steps": ["Apply at the RTO using Form 31 to transfer ownership to the heir.",
                  "Update the insurance policy to the new owner."],
        "where": "Regional Transport Office (RTO)."},
    "loan": {
        "label": "Loans & liabilities",
        "documents": ["Death certificate", "Loan account statement",
                      "Any loan-protection / home-loan insurance policy"],
        "steps": ["Check whether the loan carried protection insurance — many home loans do; "
                  "if so, the cover can clear the outstanding balance.",
                  "Otherwise the debt is settled from the estate or the secured asset.",
                  "Liabilities are NOT inherited as personal debt beyond the estate's value."],
        "where": "The lender's branch / loan servicing desk."},
}
GENERIC_SUCCESSION_NOTE = ("Obtain 10+ attested copies of the death certificate up front — every "
                           "institution keeps one. A nominee is a trustee who receives the asset; "
                           "final ownership still follows the will or succession law.")

def _case_progress(c, case_id):
    rows = c.execute("SELECT status FROM succession_tasks WHERE case_id=?", (case_id,)).fetchall()
    total = len(rows)
    done = len([r for r in rows if r["status"] in ("transferred", "na")])
    return {"tasks": total, "done": done,
            "pct": round(done / total * 100) if total else 0}

class SuccessionOpenIn(BaseModel):
    person_id: str
    note: Optional[str] = None

@app.post("/api/succession/open")
def succession_open(body: SuccessionOpenIn, request: Request, user=Depends(get_user)):
    require_writer(user)
    with db() as c:
        p = c.execute("SELECT * FROM persons WHERE id=? AND family_id=? AND deleted_at IS NULL",
                      (body.person_id, user["family_id"])).fetchone()
        if not p:
            raise HTTPException(404, "Person not found")
        existing = c.execute(
            "SELECT * FROM succession_cases WHERE family_id=? AND person_id=? AND status='open' AND deleted_at IS NULL",
            (user["family_id"], body.person_id)).fetchone()
        if existing:
            return {"id": existing["id"], "existing": True}
        if p["status"] != "deceased":
            c.execute("UPDATE persons SET status='deceased' WHERE id=?", (body.person_id,))
            emit(c, user["family_id"], user["name"], "member.updated",
                 {"name": p["name"], "status": "deceased"})
        case_id = nid()
        c.execute("INSERT INTO succession_cases(id, family_id, person_id, status, note, opened_by, opened_at)"
                  " VALUES(?,?,?,?,?,?,?)",
                  (case_id, user["family_id"], body.person_id, "open", body.note, user["name"], now()))
        assets = c.execute(
            "SELECT * FROM assets WHERE family_id=? AND owner_person_id=? AND deleted_at IS NULL",
            (user["family_id"], body.person_id)).fetchall()
        for a in assets:
            c.execute("INSERT INTO succession_tasks(id, case_id, family_id, asset_id, category, title, kind,"
                      " status, updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                      (nid(), case_id, user["family_id"], a["id"], a["category"], a["title"],
                       a["kind"], "not_started", now()))
        emit(c, user["family_id"], user["name"], "succession.opened",
             {"person": p["name"], "tasks": len(assets)})
    return {"id": case_id, "tasks": len(assets)}

@app.get("/api/succession")
def succession_list(user=Depends(get_user)):
    with db() as c:
        cases = c.execute(
            "SELECT sc.*, p.name AS person_name, p.relation AS person_relation"
            " FROM succession_cases sc JOIN persons p ON p.id=sc.person_id"
            " WHERE sc.family_id=? AND sc.deleted_at IS NULL ORDER BY sc.rowid DESC",
            (user["family_id"],)).fetchall()
        out = []
        for sc in cases:
            out.append({**dict(sc), "progress": _case_progress(c, sc["id"])})
    return {"cases": out}

@app.get("/api/succession/{case_id}")
def succession_detail(case_id: str, user=Depends(get_user)):
    with db() as c:
        sc = c.execute("SELECT * FROM succession_cases WHERE id=? AND family_id=? AND deleted_at IS NULL",
                       (case_id, user["family_id"])).fetchone()
        if not sc:
            raise HTTPException(404, "Case not found")
        person = c.execute("SELECT * FROM persons WHERE id=?", (sc["person_id"],)).fetchone()
        tasks = []
        for t in c.execute("SELECT * FROM succession_tasks WHERE case_id=? ORDER BY rowid", (case_id,)):
            a = c.execute("SELECT amount, nominee, mutation, doc_location, details FROM assets WHERE id=?",
                          (t["asset_id"],)).fetchone()
            tasks.append({**dict(t), "docs": json.loads(t["docs"]) if t["docs"] else [],
                          "guidance": SUCCESSION_GUIDANCE.get(t["category"], {}),
                          "asset": dict(a) if a else {}})
        progress = _case_progress(c, case_id)
    return {"case": dict(sc), "person": dict(person) if person else {}, "tasks": tasks,
            "progress": progress, "generic_note": GENERIC_SUCCESSION_NOTE,
            "statuses": SUCCESSION_STATUSES}

class SuccessionTaskIn(BaseModel):
    status: Optional[str] = None
    claimant_person_id: Optional[str] = None
    docs: Optional[list] = None
    note: Optional[str] = None

@app.patch("/api/succession/tasks/{task_id}")
def succession_task_update(task_id: str, body: SuccessionTaskIn, user=Depends(get_user)):
    require_writer(user)
    with db() as c:
        t = c.execute("SELECT * FROM succession_tasks WHERE id=? AND family_id=?",
                      (task_id, user["family_id"])).fetchone()
        if not t:
            raise HTTPException(404, "Task not found")
        if body.status is not None and body.status not in SUCCESSION_STATUSES:
            raise HTTPException(400, "Unknown status")
        status = body.status if body.status is not None else t["status"]
        claimant = body.claimant_person_id if body.claimant_person_id is not None else t["claimant_person_id"]
        if claimant and not person_in_family(c, claimant, user["family_id"]):
            raise HTTPException(400, "Claimant must be a member of your family")
        docs = json.dumps(body.docs) if body.docs is not None else t["docs"]
        note = body.note if body.note is not None else t["note"]
        c.execute("UPDATE succession_tasks SET status=?, claimant_person_id=?, docs=?, note=?,"
                  " updated_by=?, updated_at=? WHERE id=? AND family_id=?",
                  (status, claimant, docs, note, user["name"], now(), task_id, user["family_id"]))
        if body.status is not None:
            emit(c, user["family_id"], user["name"], "succession.task_updated",
                 {"title": t["title"], "status": status})
    return {"ok": True}

class SuccessionCloseIn(BaseModel):
    reopen: bool = False

@app.post("/api/succession/{case_id}/close")
def succession_close(case_id: str, body: SuccessionCloseIn, user=Depends(get_user)):
    require_writer(user)
    with db() as c:
        sc = c.execute("SELECT * FROM succession_cases WHERE id=? AND family_id=? AND deleted_at IS NULL",
                       (case_id, user["family_id"])).fetchone()
        if not sc:
            raise HTTPException(404, "Case not found")
        if body.reopen:
            c.execute("UPDATE succession_cases SET status='open', closed_at=NULL WHERE id=?", (case_id,))
            emit(c, user["family_id"], user["name"], "succession.reopened", {})
        else:
            c.execute("UPDATE succession_cases SET status='closed', closed_at=? WHERE id=?", (now(), case_id))
            emit(c, user["family_id"], user["name"], "succession.closed", {})
    return {"ok": True}

# ───────────────────────── report ─────────────────────────

@app.get("/api/report")
def report(user=Depends(get_user)):
    with db() as c:
        members = [dict(r) for r in c.execute(
            "SELECT * FROM persons WHERE family_id=? AND deleted_at IS NULL", (user["family_id"],))]
        assets = [dict(r) for r in c.execute(
            "SELECT * FROM assets WHERE family_id=? AND deleted_at IS NULL", (user["family_id"],))]
        checks = [dict(r) for r in c.execute(
            "SELECT * FROM checks WHERE family_id=?", (user["family_id"],))]
    for a in assets:
        a["flags"] = flags_for(a)
        a["extra"] = json.loads(a["extra"]) if a.get("extra") else {}
    only_assets = [a for a in assets if a["kind"] == "asset"]
    clean = len([a for a in only_assets if not a["flags"]])
    done = len([k for k in checks if k["done"]])
    score = 0
    if only_assets or done:
        score = round(((clean / len(only_assets) if only_assets else 0) * 0.6 + (done / 9) * 0.4) * 100)
    net = sum(a["amount"] or 0 for a in only_assets) - \
          sum(a["amount"] or 0 for a in assets if a["kind"] == "liability")
    return {"members": members, "assets": assets, "checks": checks,
            "score": score, "net_worth": net, "generated": now()}

# ───────────────────────── static ─────────────────────────

@app.get("/")
def index():
    return FileResponse("static/index.html")

app.mount("/static", StaticFiles(directory="static"), name="static")
