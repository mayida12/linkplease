from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import rules, webhook, stats

app = FastAPI(title="LinkPlease Instagram Automation")

# Allow the local React dashboard (Part - optional frontend) to call the API
# from a different port during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rules.router)
app.include_router(webhook.router)
app.include_router(stats.router)


@app.get("/health")
def health():
    return {"status": "ok"}
