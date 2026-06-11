"""
Family Ledger — backend (MVP v1)
FastAPI + SQLite. Event-logged mutations, confirm-before-commit drafts,
phone+OTP auth (dev mode), family workspace with roles & invites.

Run:  uvicorn app:app --reload --host 0.0.0.0 --port 8000
Dev OTP: printed to console (and returned in response when DEV_MODE=1).
Optional: set ANTHROPIC_API_KEY to enable AI extraction (text + documents).
"""
import os, json, sqlite3, secrets, hashlib, time, re
from datetime import datetime, timedelta
from contextlib import contextmanager
from typing import Optional

import httpx
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

DB_PATH = os.environ.get("FL_DB", "family.db")
VAULT_DIR = os.environ.get("FL_VAULT", "vault")
DEV_MODE = os.environ.get("DEV_MODE", "1") == "1"
# .strip() guards against a trailing newline/space pasted into the host's
# env var UI (e.g. Railway) — a present-but-invalid key is the most common
# cause of "key is set but extraction says it isn't".
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
MODEL = os.environ.get("FL_MODEL", "claude-sonnet-4-6").strip()
print(f"[boot] AI extraction {'ENABLED' if ANTHROPIC_API_KEY else 'DISABLED (ANTHROPIC_API_KEY not set)'}; model={MODEL}")

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
"""

@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
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
                 "ALTER TABLE persons ADD COLUMN story TEXT"):
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

# ───────────────────────── auth helpers ─────────────────────────

def get_user(request: Request):
    token = request.headers.get("authorization", "").replace("Bearer ", "")
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
                "family_id": u["family_id"], "role": u["role"],
                "name": p["name"] if p else u["phone"]}

def require_writer(user):
    if user["role"] == "viewer":
        raise HTTPException(403, "Viewers cannot make changes")

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

@app.get("/api/me")
def me(user=Depends(get_user)):
    with db() as c:
        fam = c.execute("SELECT name FROM families WHERE id=?", (user["family_id"],)).fetchone()
    return {**user, "family_name": fam["name"] if fam else ""}

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
    aid = nid()
    with db() as c:
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
    with db() as c:
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

EXTRACT_PROMPT = """You extract structured records from a Hindi/Hinglish/English family conversation transcript for an Indian family asset register. Return ONLY a JSON array, no prose, no markdown fences. Each element:
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

@app.post("/api/ingest/document")
async def ingest_document(file: UploadFile = File(...), user_token: str = Form(...)):
    # multipart can't easily carry the auth header from fetch FormData in some setups; accept token in form
    class R:  # minimal shim
        headers = {"authorization": f"Bearer {user_token}"}
    user = get_user(R())
    require_writer(user)
    data = await file.read()
    if len(data) > 8_000_000:
        raise HTTPException(400, "File too large (max 8 MB)")
    sha = hashlib.sha256(data).hexdigest()
    with db() as c:
        dup = c.execute("SELECT id FROM documents WHERE sha256=? AND family_id=?",
                        (sha, user["family_id"])).fetchone()
        if dup:
            return {"duplicate": True, "note": "This document is already in the vault."}
    ext = os.path.splitext(file.filename or "doc.jpg")[1] or ".jpg"
    path = os.path.join(VAULT_DIR, sha + ext)
    with open(path, "wb") as f:
        f.write(data)
    doc_id = nid()
    media = file.content_type or "image/jpeg"
    items = None
    if media.startswith("image/"):
        import base64
        items = claude_extract("", base64.b64encode(data).decode(), media)
    created = []
    with db() as c:
        c.execute("INSERT INTO documents(id, family_id, filename, sha256, doc_type, uploaded_by, created_at)"
                  " VALUES(?,?,?,?,?,?,?)",
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
            c.execute("UPDATE drafts SET status='confirmed' WHERE id=?", (did,))
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
        c.execute("UPDATE drafts SET status='confirmed' WHERE id=?", (did,))
    return {"ok": True}

@app.post("/api/drafts/{did}/reject")
def reject_draft(did: str, user=Depends(get_user)):
    require_writer(user)
    with db() as c:
        c.execute("UPDATE drafts SET status='rejected' WHERE id=? AND family_id=?", (did, user["family_id"]))
        emit(c, user["family_id"], user["name"], "draft.rejected", {"id": did})
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
