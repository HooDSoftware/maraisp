"""
main.py — ISP Backend (FastAPI)
Runs on Render. Connects to MikroTik RB2011 via IP Cloud DDNS.

Endpoints:
  /                   → Admin dashboard (HTML)
  /health             → Liveness + router ping
  /payments/*         → M-Pesa STK Push + callback
  /pppoe/*            → PPPoE subscriber management
  /hotspot/*          → Hotspot voucher management
  /sessions/*         → Live session viewer
  /reports/*          → Revenue & usage reports
  /docs               → Swagger UI (disable in prod if needed)
"""
import os
import logging
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
import secrets
from dotenv import load_dotenv

load_dotenv()

from database import init_db
from routers import payments, pppoe, hotspot, sessions, reports

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
log = logging.getLogger(__name__)

# ── App ───────────────────────────────────────────────────────

app = FastAPI(
    title="ISP Backend",
    description="MikroTik RB2011 ISP management — M-Pesa + WhatsApp + Gmail",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Auth ──────────────────────────────────────────────────────

security = HTTPBasic()

DASHBOARD_USER = os.getenv("DASHBOARD_USERNAME", "admin")
DASHBOARD_PASS = os.getenv("DASHBOARD_PASSWORD", "changeme")


def require_admin(credentials: HTTPBasicCredentials = Depends(security)):
    ok_user = secrets.compare_digest(credentials.username.encode(), DASHBOARD_USER.encode())
    ok_pass = secrets.compare_digest(credentials.password.encode(), DASHBOARD_PASS.encode())
    if not (ok_user and ok_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


# ── Startup ───────────────────────────────────────────────────

@app.on_event("startup")
def startup():
    init_db()
    log.info("Database initialised")
    log.info("MikroTik target: %s:%s",
             os.getenv("MIKROTIK_HOST"), os.getenv("MIKROTIK_PORT"))


# ── Public routes ─────────────────────────────────────────────

@app.get("/health")
def health():
    """Public liveness check — also pings the router."""
    from services.mikrotik import test_connection
    try:
        router_info = test_connection()
        return {"status": "ok", "router": router_info}
    except Exception as e:
        return {"status": "degraded", "router_error": str(e)}


# M-Pesa callback must be public (Daraja POSTs to it)
app.include_router(payments.router)

# ── Protected routes (admin only) ─────────────────────────────

app.include_router(
    pppoe.router,
    dependencies=[Depends(require_admin)],
)
app.include_router(
    hotspot.router,
    dependencies=[Depends(require_admin)],
)
app.include_router(
    sessions.router,
    dependencies=[Depends(require_admin)],
)
app.include_router(
    reports.router,
    dependencies=[Depends(require_admin)],
)


# ── Dashboard ─────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def dashboard(username: str = Depends(require_admin)):
    dashboard_path = os.path.join(os.path.dirname(__file__), "static", "dashboard.html")
    with open(dashboard_path) as f:
        return HTMLResponse(f.read())


# ── Entry point ───────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("APP_PORT", "8000")),
        reload=False,
    )
