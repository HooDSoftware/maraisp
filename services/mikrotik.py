"""
services/mikrotik.py
All MikroTik API operations via librouteros.
Connects through IP Cloud DDNS → WAN port 28728 → router API 8728.
"""
import os
import logging
import secrets
import string
from contextlib import contextmanager
from typing import Optional
import librouteros
from librouteros import connect

log = logging.getLogger(__name__)

def get_config():
    return {
        "host": os.getenv("MIKROTIK_HOST", "762d07842fbf.sn.mynetname.net"),
        "port": int(os.getenv("MIKROTIK_PORT", "28728")),
        "user": os.getenv("MIKROTIK_USER", "admin"),
        "password": os.getenv("MIKROTIK_PASSWORD", ""),
    }


# ── Connection ───────────────────────────────────────────────

@contextmanager
def get_api():
    """Context manager — opens and auto-closes a RouterOS API connection."""
    api = None
    config = get_config()
    try:
        api = connect(
            host=config["host"],
            port=config["port"],
            username=config["user"],
            password=config["password"],
            timeout=10,
        )
        yield api
    except librouteros.exceptions.TrapError as e:
        log.error("MikroTik TrapError: %s", e)
        raise RuntimeError(f"MikroTik error: {e}")
    except Exception as e:
        log.error("MikroTik connection failed: %s", e)
        raise RuntimeError(f"Cannot reach router at {config['host']}:{config['port']} — {e}")
    finally:
        if api:
            try:
                api.close()
            except Exception:
                pass


def test_connection() -> dict:
    """Quick connectivity check. Returns router identity."""
    config = get_config()
    with get_api() as api:
        identity = list(api(cmd="/system/identity/print"))
        cloud    = list(api(cmd="/ip/cloud/print"))
        return {
            "identity": identity[0].get("name") if identity else "unknown",
            "host": config["host"],
            "port": config["port"],
            "cloud_dns": cloud[0].get("dns-name") if cloud else config["host"],
        }


# ── PPPoE helpers ────────────────────────────────────────────

PLAN_DURATION_DAYS = {
    "plan-500":  30,
    "plan-700":  30,
    "plan-1000": 30,
    "plan-1300": 30,
    "plan-grace": 2,
    "plan-captive": 0,
}


def _rand_password(length: int = 12) -> str:
    chars = string.ascii_letters + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))


def pppoe_add(username: str, password: str, plan: str, comment: str = "") -> dict:
    """Create a new PPPoE secret (subscriber account)."""
    with get_api() as api:
        params = {
            "name":     username,
            "password": password,
            "service":  "pppoe",
            "profile":  plan,
            "comment":  comment,
        }
        api(cmd="/ppp/secret/add", **params)
    log.info("PPPoE user created: %s plan=%s", username, plan)
    return {"username": username, "password": password, "plan": plan}


def pppoe_remove(username: str) -> bool:
    """Delete a PPPoE secret by username."""
    with get_api() as api:
        items = list(api(cmd="/ppp/secret/print", **{"?name": username}))
        if not items:
            return False
        api(cmd="/ppp/secret/remove", **{".id": items[0][".id"]})
    log.info("PPPoE user removed: %s", username)
    return True


def pppoe_change_profile(username: str, new_plan: str) -> bool:
    """Switch a PPPoE user to a different profile (e.g. grace → paid plan)."""
    with get_api() as api:
        items = list(api(cmd="/ppp/secret/print", **{"?name": username}))
        if not items:
            return False
        api(cmd="/ppp/secret/set", **{".id": items[0][".id"], "profile": new_plan})
    log.info("PPPoE %s → profile %s", username, new_plan)
    return True


def pppoe_disable(username: str) -> bool:
    """Disable (not delete) a PPPoE secret."""
    with get_api() as api:
        items = list(api(cmd="/ppp/secret/print", **{"?name": username}))
        if not items:
            return False
        api(cmd="/ppp/secret/set", **{".id": items[0][".id"], "disabled": "true"})
    return True


def pppoe_enable(username: str) -> bool:
    """Re-enable a disabled PPPoE secret."""
    with get_api() as api:
        items = list(api(cmd="/ppp/secret/print", **{"?name": username}))
        if not items:
            return False
        api(cmd="/ppp/secret/set", **{".id": items[0][".id"], "disabled": "false"})
    return True


def pppoe_list() -> list:
    """Return all PPPoE secrets."""
    with get_api() as api:
        return list(api(cmd="/ppp/secret/print"))


def pppoe_kick(username: str) -> bool:
    """Disconnect an active PPPoE session (forces reconnect)."""
    with get_api() as api:
        sessions = list(api(cmd="/ppp/active/print", **{"?name": username}))
        if not sessions:
            return False
        api(cmd="/ppp/active/remove", **{".id": sessions[0][".id"]})
    log.info("PPPoE session kicked: %s", username)
    return True


# ── Active Sessions ──────────────────────────────────────────

def get_active_pppoe() -> list:
    """Return all active PPPoE sessions."""
    with get_api() as api:
        return list(api(cmd="/ppp/active/print"))


def get_active_hotspot() -> list:
    """Return all active hotspot sessions."""
    with get_api() as api:
        return list(api(cmd="/ip/hotspot/active/print"))


def hotspot_kick(session_id: str) -> bool:
    """Remove an active hotspot session by .id."""
    with get_api() as api:
        api(cmd="/ip/hotspot/active/remove", **{".id": session_id})
    return True


# ── Hotspot users ────────────────────────────────────────────

def hotspot_add_user(username: str, password: str, profile: str, comment: str = "") -> dict:
    """Add a hotspot user (voucher)."""
    with get_api() as api:
        api(
            cmd="/ip/hotspot/user/add",
            name=username,
            password=password,
            profile=profile,
            comment=comment,
        )
    log.info("Hotspot user created: %s profile=%s", username, profile)
    return {"username": username, "password": password, "profile": profile}


def hotspot_remove_user(username: str) -> bool:
    with get_api() as api:
        items = list(api(cmd="/ip/hotspot/user/print", **{"?name": username}))
        if not items:
            return False
        api(cmd="/ip/hotspot/user/remove", **{".id": items[0][".id"]})
    return True


def hotspot_list_users() -> list:
    with get_api() as api:
        return list(api(cmd="/ip/hotspot/user/print"))


# ── Router stats ─────────────────────────────────────────────

def get_router_resource() -> dict:
    """CPU, memory, uptime."""
    with get_api() as api:
        res = list(api(cmd="/system/resource/print"))
        return res[0] if res else {}


def get_interface_stats() -> list:
    with get_api() as api:
        return list(api(cmd="/interface/print", **{"stats": ""}))
