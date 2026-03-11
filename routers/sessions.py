"""
routers/sessions.py
Live session management.
GET  /sessions/pppoe         — active PPPoE sessions
GET  /sessions/hotspot       — active hotspot sessions
POST /sessions/pppoe/kick/{username}
POST /sessions/hotspot/kick/{session_id}
GET  /sessions/router        — router CPU/memory/uptime
"""
from fastapi import APIRouter, HTTPException
from services import mikrotik

router = APIRouter(prefix="/sessions", tags=["Sessions"])


@router.get("/pppoe")
def active_pppoe():
    try:
        sessions = mikrotik.get_active_pppoe()
        return {
            "count":    len(sessions),
            "sessions": sessions,
        }
    except RuntimeError as e:
        raise HTTPException(502, str(e))


@router.get("/hotspot")
def active_hotspot():
    try:
        sessions = mikrotik.get_active_hotspot()
        return {
            "count":    len(sessions),
            "sessions": sessions,
        }
    except RuntimeError as e:
        raise HTTPException(502, str(e))


@router.post("/pppoe/kick/{username}")
def kick_pppoe(username: str):
    try:
        ok = mikrotik.pppoe_kick(username)
        return {"success": ok, "message": "Kicked" if ok else "No active session found"}
    except RuntimeError as e:
        raise HTTPException(502, str(e))


@router.post("/hotspot/kick/{session_id}")
def kick_hotspot(session_id: str):
    try:
        mikrotik.hotspot_kick(session_id)
        return {"success": True}
    except RuntimeError as e:
        raise HTTPException(502, str(e))


@router.get("/router")
def router_health():
    try:
        res = mikrotik.get_router_resource()
        ifaces = mikrotik.get_interface_stats()
        return {"resource": res, "interfaces": ifaces}
    except RuntimeError as e:
        raise HTTPException(502, str(e))
