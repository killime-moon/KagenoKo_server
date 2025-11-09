from fastapi import APIRouter, HTTPException, Header
from database import users
from datetime import datetime, timedelta
import os

router = APIRouter()

def reset_if_needed(user):
    """Réinitialise le quota si plus de 7 jours sont passés."""
    last_reset_str = user.get("last_reset")
    if not last_reset_str:
        return  # rien à faire si jamais enregistré

    try:
        last_reset = datetime.fromisoformat(last_reset_str)
    except Exception:
        # si format incorrect, on remet la date actuelle
        last_reset = datetime.utcnow()

    now = datetime.utcnow()
    delta = now - last_reset

    if delta.days >= 7:
        # Détermine le quota selon le tier
        tier = user.get("tier_name", "aucun").lower()
        if "unlimited" in tier:
            new_quota = 5000
        elif "premium" in tier:
            new_quota = 500
        else:
            new_quota = 50

        # Mise à jour dans la base
        users.update_one(
            {"patreon_id": user["patreon_id"]},
            {"$set": {"quota": new_quota, "last_reset": now.isoformat()}}
        )

        # Met à jour l'objet en mémoire pour le retour
        user["quota"] = new_quota
        user["last_reset"] = now.isoformat()

@router.post("/interact")
async def interact(google_id: str):
    user = users.find_one({"patreon_id": google_id})
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    reset_if_needed(user)

    if user["quota"] <= 0:
        return {"status": "quota_exceeded", "remaining": 0}

    user["quota"] -= 1
    users.update_one({"patreon_id": google_id}, {"$set": {"quota": user["quota"]}})
    return {"status": "ok", "remaining": user["quota"]}

@router.get("/remain")
async def get_quota(google_id: str):
    user = users.find_one({"patreon_id": google_id})
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")
    reset_if_needed(user)
    return {"remaining": user["quota"]}

@router.post("/admin/set_quota")
async def set_quota(google_id: str, new_quota: int, authorization: str = Header(None)):
    if authorization != f"Bearer {os.getenv('ADMIN_SECRET')}":
        raise HTTPException(status_code=401, detail="unauthorized")

    result = users.update_one({"patreon_id": google_id}, {"$set": {"quota": new_quota}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="user_not_found")

    return {"message": "quota_updated", "patreon_id": google_id, "new_quota": new_quota}




