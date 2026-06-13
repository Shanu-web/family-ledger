# Family Ledger — MVP v1

Voice-first family asset register. FastAPI + SQLite + vanilla JS. Implements W1–W5 of the workflow spec: **passkey (WebAuthn) sign-in** with register/invite/claim/add-device branches, family workspace with roles, append-only event log, confirm-before-commit ingestion (voice/text/document), red flags, discovery checklist, audit report, an **encrypted document vault**, and **succession (transmission) flows**.

## Run

```bash
cd family-ledger
pip install -r requirements.txt        # fastapi uvicorn python-multipart httpx cryptography webauthn
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000. Passkeys require a **secure context**: `localhost` works, and the deployed HTTPS URL works — but `http://<laptop-ip>:8000` does **not**, so test phones against the deployed URL.

**Sign-in is device-based (passkeys), no SMS.** You sign in with your phone's fingerprint / Face ID. There are **no per-message SMS costs and no DLT registration**. A brand-new number starts its own family (you become owner); joining an existing family needs an owner invite — that invite is what vouches for you in place of an SMS.

**Dev mode (default, `DEV_MODE=1`):** a passkey-free fallback is available — a "use a test code" link signs you in with OTP `123456` (printed to the console). Handy for automated tests and for browsers without a passkey authenticator. Turn it off (`DEV_MODE=0`) in production so only passkeys are accepted.

**AI extraction (optional but recommended):**
```bash
export ANTHROPIC_API_KEY=sk-ant-...
```
With the key set, spoken/typed Hinglish and uploaded document photos are extracted by Claude into structured drafts. Without it, a basic keyword parser runs as fallback (clearly marked, low confidence).

**Voice input:** uses the browser's built-in speech recognition (`hi-IN`) — works in Chrome/Edge. No key needed. Production would swap this for Sarvam/Bhashini server-side STT.

## Try this flow

1. Enter any 10-digit number → "Continue with this device" → your browser prompts to create a passkey (fingerprint / Face ID) → name yourself → you're the Owner. (On `localhost` the OS shows a passkey dialog; in automated tests the dev OTP fallback is used.)
2. Family tab → add Father with his real phone number. Your registered device shows under "Your sign-in devices".
3. Capture tab → tap the mic and say: *"Patna mein ghar hai papa ke naam, home loan 32 lakh chal raha hai, aur ek LIC policy hai mummy ki"* → review drafts → edit owner/amounts → Confirm.
4. Register tab → see red flags (mutation pending, nominee unknown).
5. Family tab → invite your wife's number → she opens the app on her phone, enters that number, and sets up a passkey → lands in the same workspace (the invite vouches for her — no SMS).
6. Father enters his own number → the app offers his existing profile to **claim**, then he enrols a passkey (Person ≠ User in action).
7. Vault tab → set a passphrase (save the recovery code) → upload a document photo from Capture (encrypted).
8. Succession tab → pick a member → build the transmission plan → print.

## Architecture (maps to family-ledger-workflow-spec.md)

- **Event log** (`events` table): every mutation appends an event with actor + payload; activity feed reads from it; idempotency via unique `client_key`.
- **Confirm gate** (`drafts` table): AI output never writes to the register directly; user edits + confirms each draft.
- **Soft deletes** everywhere (`deleted_at`); nothing is destroyed.
- **Passkey auth** (spec W1, `credentials` + `webauthn_flows` tables): WebAuthn replaces SMS. `begin` resolves the number to a branch — **authenticate** (returning device), or **register** a credential for `join_invite` / `claim` / `add_device` / new-family. Each device stores only its **public** key server-side; the private key never leaves the phone. Enrolment trust comes from the owner's invite, not a carrier. RP ID/origin derive from the request (override with `FL_RP_ID` / `FL_ORIGIN`). A DEV-only OTP path remains for testing. Lost device → owner re-invites the number to enrol a new one; synced passkeys (iCloud/Google) roam automatically.
- **Encrypted vault** (`vault_keys` table, W5): documents are encrypted at rest with AES-256-GCM under a random per-family data key (DEK). The DEK is **envelope-wrapped twice** — once by a key derived from the family passphrase (scrypt), once by a one-time recovery code — so a forgotten passphrase is recoverable but losing both is not. The server stores only wrapped keys + ciphertext and cannot read documents on its own; the unlocked DEK lives only in process memory, keyed by session, and auto-expires after 30 min. Files are deduped by plaintext content hash.
- **Succession / transmission** (`succession_cases` + `succession_tasks`, W5): marking a member deceased opens a case that auto-creates a per-asset transmission task. Each task carries India-specific guidance (documents, steps, where to go) for its category — bank, insurance, EPF, property, demat, gold, vehicle, loan — a claimant/nominee, a document checklist, and a status pipeline (not started → gathering → filed → transferred). Produces a printable plan. General procedural guidance, not legal advice.
- **Roles**: owner / member / viewer enforced server-side.

## Deploy (Railway)

1. Push this repo to GitHub → Railway → New Project → Deploy from GitHub repo. The `Procfile` is picked up automatically.
2. Variables: set `ANTHROPIC_API_KEY` (AI extraction) and **`DEV_MODE=0`** so only passkeys are accepted (the OTP test-code fallback is disabled). Set `FL_RP_ID` to your domain (e.g. `myfamily.up.railway.app`) and `FL_ORIGIN` to `https://<that-domain>` for stable WebAuthn verification behind the proxy.
3. SQLite is wiped on every redeploy unless you attach a Volume: mount it at `/data`, then set `FL_DB=/data/family.db` and `FL_VAULT=/data/vault`. The volume also preserves the encrypted document files.
4. Voice input and passkeys both work on the deployed URL (https = secure context). No SMS provider or DLT registration is needed.

## Document vault & succession (W5)

**Vault — set it up first to store documents.** Owner opens the **Vault** tab and chooses a family passphrase; the app shows a one-time **recovery code** (save it — it's the only way back in if the passphrase is forgotten). Anyone needing to view documents unlocks with the passphrase; the vault auto-locks after 30 min. Uploads from Capture are encrypted before touching the disk. If the passphrase is lost, the owner resets it from the recovery code under "Forgot the passphrase?".

**Succession.** When a member passes, open the **Succession** tab → pick the member → "Build succession plan". The member is marked deceased and a transmission task is created for every asset in their name, each with the documents and steps that Indian institution needs. Tick documents off, set the claimant, move each through the status pipeline, and print the plan to carry to each bank/office.

> Because the vault uses per-family passphrase encryption (the server genuinely cannot read documents), the unlocked key is held in memory by a single server process — run one uvicorn worker, and attach a persistent volume on Railway so the encrypted files survive redeploys.

## Known limits (deliberate, v1)

Sarvam STT, branch privacy scoping, field-level merge conflicts, and export — all specced, not built. Sign-in is passkey-based (no SMS); the only remaining fallback is the DEV-mode OTP test code, which must be disabled in production (`DEV_MODE=0`). Multi-device relies on synced passkeys or an owner re-invite; there is no account recovery if a user loses every device and has no synced passkey and no owner to re-invite. Vault encryption protects data at rest (stolen disk/backup), not a fully-compromised live server with the vault already unlocked. The unlocked vault key and any in-flight passkey challenge live in one server process — run a single uvicorn worker. Single-server SQLite is fine for family-scale testing.
