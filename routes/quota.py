from fastapi import APIRouter, HTTPException, Header
from database import users
from datetime import datetime, timedelta
import requests
import os

router = APIRouter()

def get_current_tier(access_token: str):
    """Récupère le tier actuel de l'utilisateur via l'API Patreon."""
    res = requests.get(
        "https://www.patreon.com/api/oauth2/v2/identity",
        headers={"Authorization": f"Bearer {access_token}"},
        params={
            "include": "memberships.currently_entitled_tiers",
            "fields[tier]": "title,amount_cents",
            "fields[user]": "email,full_name"
        }
    )
    data = res.json()
    included = data.get("included", [])
    tier_name = "aucun"

    for item in included:
        if item.get("type") == "tier":
            tier_name = item.get("attributes", {}).get("title", "aucun").lower()
            break

    return tier_name


def determine_quota(tier_name: str) -> int:
    """Retourne le quota selon le nom du tier."""
    tier_name = tier_name.lower()
    if "unlimited" in tier_name:
        return 5000
    elif "premium" in tier_name:
        return 500
    else:
        return 50


def reset_if_needed(user):
    """Réinitialise le quota si plus de 7 jours sont passés OU si le tier Patreon a changé."""
    if user.get("patreon_id") == CREATOR_ID:
        print(f"👑 Reset ignoré pour le créateur")
        return
    last_reset_str = user.get("last_reset")
    access_token = user.get("access_token")  # À stocker à la création / mise à jour
    if not access_token:
        print(f"⚠️ Aucun access_token enregistré pour {user.get('patreon_id')}")
        return

    # Vérifie le tier actuel sur Patreon
    try:
        current_tier = get_current_tier(access_token)
    except Exception as e:
        print(f"Erreur API Patreon: {e}")
        return

    now = datetime.utcnow()

    # Compare le tier avec celui stocké
    stored_tier = user.get("tier_name", "aucun").lower()
    tier_changed = (stored_tier != current_tier)

    # Vérifie la dernière réinitialisation
    try:
        last_reset = datetime.fromisoformat(last_reset_str)
    except Exception:
        last_reset = now - timedelta(days=8)  # Force reset si valeur invalide

    delta = now - last_reset

    if delta.days >= 7 or tier_changed:
        new_quota = determine_quota(current_tier)

        # Met à jour la base de données
        users.update_one(
            {"patreon_id": user["patreon_id"]},
            {"$set": {
                "quota": new_quota,
                "tier_name": current_tier,
                "last_reset": now.isoformat()
            }}
        )

        user["quota"] = new_quota
        user["tier_name"] = current_tier
        user["last_reset"] = now.isoformat()

        print(f"✅ Quota réinitialisé pour {user['patreon_id']} ({current_tier})")

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








