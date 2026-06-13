"""Passkey (WebAuthn) ceremony tests, driven by a simulated authenticator.
Run in-process: ANTHROPIC_API_KEY="" FL_DB=/tmp/pk.db python test_passkey.py"""
import importlib.util, json
from soft_webauthn import SoftWebauthnDevice
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url

spec = importlib.util.spec_from_file_location("app", "app.py")
app = importlib.util.module_from_spec(spec); spec.loader.exec_module(app)
from starlette.testclient import TestClient
c = TestClient(app.app)                       # Host header -> 'testserver'
ORIGIN = "http://testserver"

results = []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS" if cond else "FAIL"), "-", name,
                                       ("| " + str(detail)[:160] if detail and not cond else ""))

def reg_cred(options):
    """Simulate navigator.credentials.create() from server options."""
    dev = SoftWebauthnDevice()
    pk = options
    att = dev.create({"publicKey": {
        "rp": pk["rp"],
        "user": {"id": base64url_to_bytes(pk["user"]["id"]), "name": pk["user"]["name"],
                 "displayName": pk["user"]["displayName"]},
        "challenge": base64url_to_bytes(pk["challenge"]),
        "pubKeyCredParams": pk["pubKeyCredParams"]}}, ORIGIN)
    cred = {"id": bytes_to_base64url(att["rawId"]), "rawId": bytes_to_base64url(att["rawId"]),
            "type": "public-key", "clientExtensionResults": {},
            "response": {"clientDataJSON": bytes_to_base64url(att["response"]["clientDataJSON"]),
                         "attestationObject": bytes_to_base64url(att["response"]["attestationObject"])}}
    return dev, cred

def auth_cred(dev, options):
    """Simulate navigator.credentials.get() with an existing device."""
    pk = options
    asrt = dev.get({"publicKey": {
        "challenge": base64url_to_bytes(pk["challenge"]), "rpId": pk["rpId"],
        "allowCredentials": [{"type": "public-key", "id": base64url_to_bytes(a["id"])}
                             for a in pk.get("allowCredentials", [])]}}, ORIGIN)
    uh = asrt["response"].get("userHandle")
    return {"id": bytes_to_base64url(asrt["rawId"]), "rawId": bytes_to_base64url(asrt["rawId"]),
            "type": "public-key", "clientExtensionResults": {},
            "response": {"clientDataJSON": bytes_to_base64url(asrt["response"]["clientDataJSON"]),
                         "authenticatorData": bytes_to_base64url(asrt["response"]["authenticatorData"]),
                         "signature": bytes_to_base64url(asrt["response"]["signature"]),
                         "userHandle": bytes_to_base64url(uh) if uh else None}}

H = lambda t: {"authorization": f"Bearer {t}"}

# 1) brand-new number → register a new family (owner self-enrols a device)
b = c.post("/api/auth/passkey/begin", json={"phone": "9000000001"}).json()
check("new number -> register ceremony", b["mode"] == "register" and b["next"] == "register", b)
devA, cred = reg_cred(b["options"])
r = c.post("/api/auth/passkey/complete", json={"handle": b["handle"], "credential": cred,
           "action": "register", "name": "Papa Ji", "family_name": "Test Fam", "device_label": "Papa phone"})
check("register completes -> token", r.status_code == 200 and r.json().get("token"), r.text)
OWNER = r.json()["token"]
check("owner is owner role", c.get("/api/me", headers=H(OWNER)).json()["role"] == "owner", "")

# 2) returning owner, same device → authenticate (biometric)
b = c.post("/api/auth/passkey/begin", json={"phone": "9000000001"}).json()
check("returning number -> authenticate", b["mode"] == "authenticate", b)
r = c.post("/api/auth/passkey/complete", json={"handle": b["handle"], "credential": auth_cred(devA, b["options"])})
check("authenticate -> token", r.status_code == 200 and r.json().get("token"), r.text)
check("same family on re-login", c.get("/api/me", headers=H(r.json()["token"])).json()["family_name"] == "Test Fam", "")

# 3) unknown device with no invite is refused (owner-vouch rule)
#    simulate by registering a user then clearing the begin path: a 2nd new number with an invite
c.post("/api/invites", headers=H(OWNER), json={"phone": "9000000002", "role": "member"})
b = c.post("/api/auth/passkey/begin", json={"phone": "9000000002"}).json()
check("invited number -> join_invite ceremony", b["mode"] == "register" and b["next"] == "join_invite", b)
check("join_invite asks for name", b.get("need_name") is True, b)
devB, cred = reg_cred(b["options"])
r = c.post("/api/auth/passkey/complete", json={"handle": b["handle"], "credential": cred,
           "action": "join_invite", "name": "Beta", "device_label": "Beta phone"})
check("join via invite -> token", r.status_code == 200 and r.json().get("token"), r.text)
MEMBER = r.json()["token"]
check("member lands in owner's family",
      c.get("/api/me", headers=H(MEMBER)).json()["family_name"] == "Test Fam", "")

# 4) a number with an account but NO device here and NO invite → blocked
c.post("/api/invites", headers=H(OWNER), json={"phone": "9000000002", "role": "member"})  # consumed already? new invite
# remove member's device to simulate a new phone with no synced passkey
with app.db() as conn:
    uid = conn.execute("SELECT id FROM users WHERE phone='9000000002'").fetchone()["id"]
    conn.execute("DELETE FROM credentials WHERE user_id=?", (uid,))
    conn.execute("UPDATE invites SET used_at='x' WHERE phone='9000000002'")  # no fresh invite
b = c.post("/api/auth/passkey/begin", json={"phone": "9000000002"}).json()
check("account w/o device & no invite -> blocked", b["mode"] == "blocked", b)

# 5) add-device: owner re-invites that number → add-begin enrols a new device
c.post("/api/invites", headers=H(OWNER), json={"phone": "9000000002", "role": "member"})
b = c.post("/api/auth/passkey/add-begin", json={"phone": "9000000002"}).json()
check("add-begin returns register ceremony", b["mode"] == "register" and b["next"] == "add_device", b)
devB2, cred = reg_cred(b["options"])
r = c.post("/api/auth/passkey/complete", json={"handle": b["handle"], "credential": cred,
           "action": "add_device", "device_label": "Beta new phone"})
check("add_device -> token", r.status_code == 200 and r.json().get("token"), r.text)

# 6) device management
devs = c.get("/api/credentials", headers=H(OWNER)).json()["devices"]
check("owner has 1 registered device", len(devs) == 1, devs)
check("cannot remove only device",
      c.delete(f"/api/credentials/{devs[0]['id']}", headers=H(OWNER)).status_code == 400, "")

passed = sum(results)
print(f"\n{passed}/{len(results)} passed")
import sys; sys.exit(0 if passed == len(results) else 1)
