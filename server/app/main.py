"""FastAPI app — routes only.

Phase 1: only GET /v1/health is implemented.
"""

from fastapi import FastAPI

app = FastAPI(
    title="Bol Khata",
    description="Voice-first credit ledger for Pakistani kiryana shopkeepers",
    version="0.1.0",
)


@app.get("/v1/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {
        "status": "ok",
        "asr_engine": "none",
        "version": "0.1.0",
    }
