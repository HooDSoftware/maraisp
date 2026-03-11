"""
routers/pppoe.py
Full PPPoE subscriber management.
GET  /pppoe/              — list all secrets from router
POST /pppoe/              — create subscriber manually
PUT  /pppoe/{username}/profile  — change plan
POST /pppoe/{username}/kick     — disconnect active session
POST /pppoe/{username}/disable  — disable account
POST /pppoe/{username}/enable   — re-enable account
DELETE /pppoe/{username}        — delete account
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from services import mikrotik

router = APIRouter(prefix="/pppoe", tags=["PPPoE"])


class CreatePPPoE(BaseModel):
    username: str
    password: str
    plan:     str
    phone:    str = ""
    comment:  str = ""


class ChangeProfile(BaseModel):
    plan: str


@router.get("/")
def list_pppoe_users():
    try:
        users = mikrotik.pppoe_list()
        return users
    except RuntimeError as e:
        raise HTTPException(502, str(e))


@router.post("/")
def create_pppoe_user(data: CreatePPPoE):
    try:
        result = mikrotik.pppoe_add(
            username=data.username,
            password=data.password,
            plan=data.plan,
            comment=data.comment or f"phone={data.phone}",
        )
        return {"success": True, **result}
    except RuntimeError as e:
        raise HTTPException(502, str(e))


@router.put("/{username}/profile")
def change_plan(username: str, data: ChangeProfile):
    try:
        ok = mikrotik.pppoe_change_profile(username, data.plan)
        if not ok:
            raise HTTPException(404, f"User '{username}' not found")
        return {"success": True, "username": username, "new_plan": data.plan}
    except RuntimeError as e:
        raise HTTPException(502, str(e))


@router.post("/{username}/kick")
def kick_session(username: str):
    try:
        ok = mikrotik.pppoe_kick(username)
        return {"success": ok, "message": "Session disconnected" if ok else "No active session"}
    except RuntimeError as e:
        raise HTTPException(502, str(e))


@router.post("/{username}/disable")
def disable_user(username: str):
    try:
        ok = mikrotik.pppoe_disable(username)
        if not ok:
            raise HTTPException(404, f"User '{username}' not found")
        return {"success": True}
    except RuntimeError as e:
        raise HTTPException(502, str(e))


@router.post("/{username}/enable")
def enable_user(username: str):
    try:
        ok = mikrotik.pppoe_enable(username)
        if not ok:
            raise HTTPException(404, f"User '{username}' not found")
        return {"success": True}
    except RuntimeError as e:
        raise HTTPException(502, str(e))


@router.delete("/{username}")
def delete_user(username: str):
    try:
        ok = mikrotik.pppoe_remove(username)
        if not ok:
            raise HTTPException(404, f"User '{username}' not found")
        return {"success": True}
    except RuntimeError as e:
        raise HTTPException(502, str(e))
