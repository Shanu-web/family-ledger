"""Family Ledger E2E API tests. Run against a fresh DB."""
import httpx, sys

B = "http://127.0.0.1:8000"
c = httpx.Client(base_url=B, timeout=30, trust_env=False)
results = []

def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("PASS" if cond else "FAIL"), "-", name, ("| " + str(detail)[:160] if detail and not cond else ""))

def otp_login(phone):
    r = c.post("/api/auth/request-otp", json={"phone": phone}).json()
    return c.post("/api/auth/verify", json={"phone": phone, "otp": r["dev_otp"]}).json()

H = lambda t: {"authorization": f"Bearer {t}"}

# ── W1 auth ──────────────────────────────────────────
r = c.post("/api/auth/request-otp", json={"phone": "12345"})
check("reject invalid phone", r.status_code == 400, r.text)

r = c.post("/api/auth/request-otp", json={"phone": "+91 99999 00001"})
check("request OTP (normalizes +91/spaces)", r.status_code == 200 and r.json().get("dev_otp") == "123456", r.text)

# rate limit: 5 wrong attempts then 429
last = None
for i in range(6):
    last = c.post("/api/auth/verify", json={"phone": "9999900001", "otp": "000000"})
check("OTP rate limit after 5 wrong attempts", last.status_code == 429, f"got {last.status_code}")

# fresh OTP, correct verify -> register branch
v = otp_login("9999900001")
check("new phone -> register branch", v.get("next") == "register" and v.get("vtoken"), v)

r = c.post("/api/auth/complete", json={"vtoken": v["vtoken"], "action": "register",
                                       "name": "Shanu Choudhary", "family_name": "Choudhary Family"})
check("register creates owner", r.status_code == 200, r.text)
OWNER = r.json()["token"]

me = c.get("/api/me", headers=H(OWNER)).json()
check("/api/me owner role + family", me.get("role") == "owner" and me.get("family_name") == "Choudhary Family", me)
OWNER_PID = me["person_id"]

r = c.get("/api/me")
check("no token -> 401", r.status_code == 401)

# vtoken reuse should fail (deleted on complete)
r = c.post("/api/auth/complete", json={"vtoken": v["vtoken"], "action": "register", "name": "X"})
check("vtoken single-use", r.status_code == 400, r.text)

# add father with phone (for claim test)
r = c.post("/api/members", headers=H(OWNER),
           json={"name": "Ramesh Choudhary", "relation": "Father", "phone": "9999900002"})
check("add member (father)", r.status_code == 200, r.text)
FATHER_PID = r.json()["id"]

# invite wife
r = c.post("/api/invites", headers=H(OWNER), json={"phone": "9999900003", "role": "member"})
check("owner can invite", r.status_code == 200, r.text)

# wife signs in -> join_invite branch
v = otp_login("9999900003")
check("invited phone -> join_invite branch", v.get("next") == "join_invite" and v.get("family_name") == "Choudhary Family", v)
r = c.post("/api/auth/complete", json={"vtoken": v["vtoken"], "action": "join_invite", "name": "Priya"})
check("join via invite", r.status_code == 200, r.text)
WIFE = r.json()["token"]
me_w = c.get("/api/me", headers=H(WIFE)).json()
check("wife in same family as member", me_w.get("family_id") == me.get("family_id") and me_w.get("role") == "member", me_w)

# father signs in -> claim branch
v = otp_login("9999900002")
check("father phone -> claim branch", v.get("next") == "claim" and v.get("candidates"), v)
r = c.post("/api/auth/complete", json={"vtoken": v["vtoken"], "action": "claim",
                                       "person_id": v["candidates"][0]["id"]})
check("claim existing profile", r.status_code == 200, r.text)
FATHER = r.json()["token"]
me_f = c.get("/api/me", headers=H(FATHER)).json()
check("claim links same person_id", me_f.get("person_id") == FATHER_PID, me_f)

# returning user -> session branch
v = otp_login("9999900001")
check("returning user -> session branch", v.get("next") == "session" and v.get("token"), v)

# non-owner cannot invite
r = c.post("/api/invites", headers=H(WIFE), json={"phone": "9999900004"})
check("member cannot invite (403)", r.status_code == 403, r.text)

# viewer invite + role enforcement
r = c.post("/api/invites", headers=H(OWNER), json={"phone": "9999900005", "role": "viewer"})
v = otp_login("9999900005")
r = c.post("/api/auth/complete", json={"vtoken": v["vtoken"], "action": "join_invite", "name": "Dadi"})
VIEWER = r.json()["token"]
r = c.post("/api/members", headers=H(VIEWER), json={"name": "X"})
check("viewer cannot write (403)", r.status_code == 403, r.text)

# ── W2/W3 capture -> draft -> confirm ────────────────
r = c.post("/api/ingest/text", headers=H(OWNER),
           json={"transcript": "Patna mein ghar hai papa ke naam, home loan 32 lakh chal raha hai, aur ek LIC policy hai"})
j = r.json()
check("ingest creates drafts (fallback engine)", r.status_code == 200 and len(j.get("drafts", [])) >= 2, j)
drafts = j["drafts"]
prop = next((d for d in drafts if d["category"] == "property"), None)
loan = next((d for d in drafts if d["category"] == "loan"), None)
lic = next((d for d in drafts if d["category"] == "insurance"), None)
check("fallback found property+loan+insurance", prop and loan and lic, [d["category"] for d in drafts])
check("amount parsed (32 lakh = 3,200,000)", any((d.get("amount") or 0) == 3200000 for d in drafts),
      [d.get("amount") for d in drafts])

r = c.post("/api/ingest/text", headers=H(OWNER), json={"transcript": "   "})
check("empty transcript -> 400", r.status_code == 400, r.text)

# register has nothing yet (confirm gate)
a = c.get("/api/assets", headers=H(OWNER)).json()["assets"]
check("confirm gate: no assets before confirm", len(a) == 0, a)

# confirm property with edited owner -> father
p = dict(prop); p["owner_person_id"] = FATHER_PID; p["title"] = "Patna house"; p.pop("id", None)
r = c.post(f"/api/drafts/{prop['id']}/confirm", headers=H(OWNER), json={"payload": p})
check("confirm property draft", r.status_code == 200, r.text)
l = dict(loan); l.pop("id", None)
c.post(f"/api/drafts/{loan['id']}/confirm", headers=H(OWNER), json={"payload": l})
r = c.post(f"/api/drafts/{lic['id']}/reject", headers=H(OWNER))
check("reject draft", r.status_code == 200, r.text)

open_drafts = c.get("/api/drafts", headers=H(OWNER)).json()["drafts"]
check("no open drafts left", len(open_drafts) == 0, open_drafts)

assets = c.get("/api/assets", headers=H(OWNER)).json()["assets"]
check("register has 2 entries after confirm", len(assets) == 2, [a["title"] for a in assets])
house = next(a for a in assets if a["category"] == "property")
check("owner edit honored (house owned by father)", house["owner_person_id"] == FATHER_PID, house)
check("red flags on property (mutation + doc location)",
      "Mutation pending" in house["flags"] and "Document location not recorded" in house["flags"], house["flags"])

# confirming same draft twice -> 404
r = c.post(f"/api/drafts/{prop['id']}/confirm", headers=H(OWNER), json={"payload": p})
check("double-confirm blocked", r.status_code == 404, r.text)

# ── assets CRUD + flags + idempotency ────────────────
r = c.post("/api/assets", headers={**H(OWNER), "idempotency-key": "fd-1"},
           json={"category": "bank", "title": "SBI FD", "owner_person_id": OWNER_PID,
                 "amount": 500000, "nominee": "yes", "doc_location": "Almirah file"})
check("add asset directly", r.status_code == 200, r.text)
fd_id = r.json()["id"]
r2 = c.post("/api/assets", headers={**H(OWNER), "idempotency-key": "fd-1"},
            json={"category": "bank", "title": "SBI FD", "owner_person_id": OWNER_PID,
                  "amount": 500000, "nominee": "yes", "doc_location": "Almirah file"})
assets = c.get("/api/assets", headers=H(OWNER)).json()["assets"]
n_fd = len([a for a in assets if a["title"] == "SBI FD"])
check("idempotency-key prevents duplicate ASSET row", n_fd == 1, f"{n_fd} SBI FD rows exist")

fd = next(a for a in assets if a["id"] == fd_id)
check("clean asset has no flags", fd["flags"] == [], fd["flags"])

r = c.patch(f"/api/assets/{fd_id}", headers=H(OWNER),
            json={"category": "bank", "title": "SBI FD renamed", "owner_person_id": OWNER_PID,
                  "amount": 600000, "nominee": "yes", "doc_location": "Almirah file"})
check("edit asset", r.status_code == 200, r.text)
r = c.delete(f"/api/assets/{fd_id}", headers=H(OWNER))
assets = c.get("/api/assets", headers=H(OWNER)).json()["assets"]
check("soft delete hides asset", all(a["id"] != fd_id for a in assets), [a["title"] for a in assets])

# wife (member) can write, viewer cannot
r = c.post("/api/ingest/text", headers=H(VIEWER), json={"transcript": "gold locker mein hai"})
check("viewer cannot ingest (403)", r.status_code == 403, r.text)

# cannot delete own profile
r = c.delete(f"/api/members/{OWNER_PID}", headers=H(OWNER))
check("cannot delete own profile", r.status_code == 400, r.text)

# member soft-delete cascades to their assets
r = c.post("/api/members", headers=H(OWNER), json={"name": "Chacha", "relation": "Other"})
ch_pid = r.json()["id"]
r = c.post("/api/assets", headers=H(OWNER), json={"category": "gold", "title": "Chacha gold",
                                                  "owner_person_id": ch_pid})
c.delete(f"/api/members/{ch_pid}", headers=H(OWNER))
assets = c.get("/api/assets", headers=H(OWNER)).json()["assets"]
check("deleting member soft-deletes their assets", all(a["title"] != "Chacha gold" for a in assets))

# ── events / checks / report ─────────────────────────
fam = c.get("/api/family", headers=H(OWNER)).json()
types = [e["type"] for e in fam["activity"]]
check("event log populated", "family.created" in types or len(types) >= 10, types[:6])
check("invite phone masked in events",
      all("9999900003" not in (e["payload"] or "") for e in fam["activity"] if e["type"] == "invite.sent"))

r = c.post("/api/checks", headers=H(OWNER), json={"id": "udgam", "done": True, "note": "no unclaimed deposits"})
ck = c.get("/api/checks", headers=H(OWNER)).json()["checks"]
check("discovery check saved", ck.get("udgam", {}).get("done") == 1, ck)

rep = c.get("/api/report", headers=H(OWNER)).json()
check("report generates", "score" in rep and "net_worth" in rep, rep.get("score"))
check("net worth = assets - liabilities", rep["net_worth"] == -3200000,  # house no amount, loan 32L
      rep["net_worth"])

# family isolation: stranger registers own family, sees nothing
v = otp_login("8888800001")
r = c.post("/api/auth/complete", json={"vtoken": v["vtoken"], "action": "register", "name": "Stranger"})
STR = r.json()["token"]
a = c.get("/api/assets", headers=H(STR)).json()["assets"]
m = c.get("/api/family", headers=H(STR)).json()["members"]
check("family isolation (stranger sees only self)", len(a) == 0 and len(m) == 1, (len(a), len(m)))

# fallback amount-proximity: each amount goes to nearest keyword, once
r = c.post("/api/ingest/text", headers=H(STR),
           json={"transcript": "Banglore me mera ek ghar hai karib 80 Lakh ka loan hai 27 lakh "
                               "every month emi 45000 and then ghar ka insurance v hai"})
ds = {d["category"]: d for d in r.json()["drafts"]}
check("proximity: house gets 80 lakh", ds.get("property", {}).get("amount") == 8000000, ds.get("property"))
check("proximity: loan gets 27 lakh (not 80)", ds.get("loan", {}).get("amount") == 2700000, ds.get("loan"))
check("proximity: insurance gets no amount", ds.get("insurance", {}).get("amount") is None, ds.get("insurance"))

# ── summary ──────────────────────────────────────────
fails = [r for r in results if not r[1]]
print(f"\n{len(results)-len(fails)}/{len(results)} passed")
if fails:
    print("FAILURES:")
    for n, _, d in fails:
        print(" -", n, "|", str(d)[:200])
sys.exit(1 if fails else 0)
