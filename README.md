# Bol Khata

Voice-first credit ledger (khata) for Pakistani kiryana shopkeepers.
The shopkeeper speaks a sale in Urdu; the system produces a structured
ledger entry in under three seconds with an audible Urdu confirmation.

Alibaba Cloud AI Hackathon 2026 · Focus area: Urdu & Regional Language Tech

## For AI coding agents

Read **AGENTS.md** first. It is the contract for this repository.

## Documentation

| File | Read when |
|---|---|
| `AGENTS.md` | Always, before any code |
| `docs/01-domain-urdu.md` | Working on the normalizer or extractor |
| `docs/02-contracts.md` | Always — frozen schemas and algorithms |
| `docs/03-build-plan.md` | Starting a phase |
| `docs/04-stack.md` | Providers, keys, free-tier limits |
| `prompts/PROMPTS.md` | Human-facing; not agent instructions |

## Quick start

```bash
cp .env.example .env          # then fill in GROQ_API_KEY (optional for local offline mode)

# 1. Server
source /mnt/data/UVCentralVenv/bin/activate
cd server
pytest tests -q
uvicorn app.main:app --reload --port 8000

# 2. Client (in a separate terminal)
cd client
npm install
npm run dev

# 3. Mobile mic access over HTTPS
cloudflared tunnel --url http://localhost:5173
```

Microphone access requires HTTPS. Test on a real Android phone through the
tunnel — `getUserMedia` fails silently over plain HTTP.
