# Family Ledger — MVP v1

Voice-first family asset register. FastAPI + SQLite + vanilla JS. Implements W1–W4 of the workflow spec: phone+OTP auth with register/invite/claim branches, family workspace with roles, append-only event log, confirm-before-commit ingestion (voice/text/document), red flags, discovery checklist, audit report.

## Run

```bash
cd family-ledger
pip install fastapi uvicorn python-multipart httpx
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 — to test from your phone, connect it to the same Wi-Fi and open http://<laptop-ip>:8000.

**Dev mode (default):** OTP is always `123456` and is shown on screen and printed in the server console. No SMS provider needed.

**AI extraction (optional but recommended):**
```bash
export ANTHROPIC_API_KEY=sk-ant-...
```
With the key set, spoken/typed Hinglish and uploaded document photos are extracted by Claude into structured drafts. Without it, a basic keyword parser runs as fallback (clearly marked, low confidence).

**Voice input:** uses the browser's built-in speech recognition (`hi-IN`) — works in Chrome/Edge. No key needed. Production would swap this for Sarvam/Bhashini server-side STT.

## Try this flow

1. Sign in with any 10-digit number → OTP 123456 → create your family (you are Owner).
2. Family tab → add Father with his real phone number.
3. Capture tab → tap the mic and say: *"Patna mein ghar hai papa ke naam, home loan 32 lakh chal raha hai, aur ek LIC policy hai mummy ki"* → review drafts → edit owner/amounts → Confirm.
4. Register tab → see red flags (mutation pending, nominee unknown).
5. Family tab → invite your wife's number → she signs in with it on her phone → lands in the same workspace.
6. Father signs in with his own number → app offers his existing profile to **claim** (Person ≠ User in action).
7. Discover tab → run UDGAM/IEPF checks → note findings.
8. Report tab → print.

## Architecture (maps to family-ledger-workflow-spec.md)

- **Event log** (`events` table): every mutation appends an event with actor + payload; activity feed reads from it; idempotency via unique `client_key`.
- **Confirm gate** (`drafts` table): AI output never writes to the register directly; user edits + confirms each draft.
- **Soft deletes** everywhere (`deleted_at`); nothing is destroyed.
- **Auth branches** (spec W1): session / join_invite / claim / register, resolved in priority order after OTP; phone existence never revealed pre-OTP; OTP rate-limited (5 attempts).
- **Vault**: uploaded documents stored by content hash (dedupe), linked to assets on confirm.
- **Roles**: owner / member / viewer enforced server-side.

## Deploy (Railway)

1. Push this repo to GitHub → Railway → New Project → Deploy from GitHub repo. The `Procfile` is picked up automatically.
2. Variables: set `ANTHROPIC_API_KEY` (for AI extraction). Keep `DEV_MODE=1` for now — real SMS OTP isn't built yet, so **anyone can sign in with any number + OTP 123456. Do not put real family data on a public deploy until real OTP is added.**
3. SQLite is wiped on every redeploy unless you attach a Volume: mount it at `/data`, then set `FL_DB=/data/family.db` and `FL_VAULT=/data/vault`.
4. Voice input works on the deployed URL (https = secure context, mic allowed).

## Known limits (deliberate, v1)

Real SMS OTP, Sarvam STT, encryption-at-rest for the vault, branch privacy scoping, succession flows (W5), field-level merge conflicts, and export — all specced, not built. Single-server SQLite is fine for family-scale testing.
