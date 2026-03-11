"""
routers/hotspot.py
Hotspot voucher management.
GET  /hotspot/users          — list router hotspot users
POST /hotspot/voucher        — generate voucher manually
GET  /hotspot/vouchers       — list DB vouchers
DELETE /hotspot/users/{name} — remove hotspot user from router
"""
import secrets
import string
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, HotspotVoucher
from services import mikrotik, whatsapp

router = APIRouter(prefix="/hotspot", tags=["Hotspot"])


def _rand(n=8):
    return "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(n))


class VoucherRequest(BaseModel):
    plan:  str          # e.g. hs-daily
    phone: str = ""     # optional — send via WhatsApp
    count: int = 1      # batch generation


@router.get("/users")
def list_hotspot_users():
    try:
        return mikrotik.hotspot_list_users()
    except RuntimeError as e:
        raise HTTPException(502, str(e))


@router.post("/voucher")
def generate_voucher(req: VoucherRequest, db: Session = Depends(get_db)):
    valid_profiles = [
        "hs-3min","hs-2hr","hs-4hr","hs-6hr",
        "hs-daily","hs-2day","hs-weekly","hs-monthly"
    ]
    if req.plan not in valid_profiles:
        raise HTTPException(400, f"Invalid hotspot plan '{req.plan}'")

    created = []
    for _ in range(max(1, min(req.count, 50))):   # cap at 50 per batch
        code = _rand(8)
        try:
            mikrotik.hotspot_add_user(
                username=code, password=code,
                profile=req.plan,
                comment=f"manual phone={req.phone}",
            )
        except RuntimeError as e:
            raise HTTPException(502, str(e))

        db.add(HotspotVoucher(code=code, plan=req.plan, phone=req.phone or None))
        created.append(code)

        if req.phone:
            msg = whatsapp.msg_hotspot_voucher(code, req.plan)
            whatsapp.send_whatsapp(req.phone, msg)

    db.commit()
    return {"success": True, "vouchers": created, "plan": req.plan}


@router.get("/vouchers")
def list_vouchers(used: bool = None, db: Session = Depends(get_db)):
    q = db.query(HotspotVoucher)
    if used is not None:
        q = q.filter_by(used=used)
    items = q.order_by(HotspotVoucher.created_at.desc()).limit(200).all()
    return [
        {
            "code": v.code, "plan": v.plan, "phone": v.phone,
            "used": v.used, "used_at": v.used_at, "created_at": v.created_at
        }
        for v in items
    ]


@router.delete("/users/{username}")
def remove_hotspot_user(username: str):
    try:
        ok = mikrotik.hotspot_remove_user(username)
        if not ok:
            raise HTTPException(404, "User not found")
        return {"success": True}
    except RuntimeError as e:
        raise HTTPException(502, str(e))
