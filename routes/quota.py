from fastapi import APIRouter, HTTPException, Header
from database import users
from datetime import datetime, timedelta
import requests
import os
import jwt, time

router = APIRouter()
LLMAPI_KEY = os.getenv("TOGETHER_API_KEY")

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
    tier_name = "free"

    for item in included:
        if item.get("type") == "tier":
            tier_name = item.get("attributes", {}).get("title", "free").lower()
            break

    return tier_name


def determine_quota(tier_name: str) -> int:
    """Retourne le quota selon le nom du tier."""
    tier_name = tier_name.lower()
    if "unlimited" in tier_name:
        return 1000
    elif "premium" in tier_name:
        return 300
    elif "ban" in tier_name:
        return 0
    else:
        return 50


def reset_if_needed(user):
    if user.get("patreon_id") == os.getenv("CREATOR_ID"):
        print(f"👑 Reset ignoré pour le créateur")
        return

    last_reset_str = user.get("last_reset")
    access_token = user.get("access_token")
    if not access_token:
        print(f"⚠️ Aucun access_token enregistré pour {user.get('patreon_id')}")
        return

    try:
        current_tier = get_current_tier(access_token)
    except Exception as e:
        print(f"Erreur API Patreon: {e}")
        return

    now = datetime.utcnow()
    stored_tier = user.get("tier_name", "free").lower()
    tier_changed = (stored_tier != current_tier)
    if stored_tier == "ban":
        tier_changed = False
        user["quota"] = 0
        users.update_one({"patreon_id": patreon_id}, {"$set": {"quota": user["quota"]}})
    # ✅ Pas de last_reset → première connexion, on initialise sans reset du quota
    if not last_reset_str:
        users.update_one(
            {"patreon_id": user["patreon_id"]},
            {"$set": {"last_reset": now.isoformat(), "tier_name": current_tier}}
        )
        print(f"🆕 Première connexion pour {user['patreon_id']}, last_reset initialisé")
        return

    try:
        last_reset = datetime.fromisoformat(last_reset_str)
    except Exception:
        # Valeur corrompue → on corrige sans toucher au quota
        users.update_one(
            {"patreon_id": user["patreon_id"]},
            {"$set": {"last_reset": now.isoformat()}}
        )
        print("Error in calcul")
        return

    delta = now - last_reset

    if delta.days >= 30 or tier_changed:
        print(stored_tier)
        print(current_tier)
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
async def interact(patreon_id: str,system_input: str, player_input: str):
    # --- Vérifie l'utilisateur ---
    user = users.find_one({"patreon_id": patreon_id})
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    reset_if_needed(user)

    quota_exceeded = False

    # --- Gérer le quota ---
    if user["quota"] > 0 and user["tier_name"] != "ban":
        user["quota"] -= 1
        users.update_one({"patreon_id": patreon_id}, {"$set": {"quota": user["quota"]}})
    else:
        quota_exceeded = True
        user["quota"] = 0
        users.update_one({"patreon_id": patreon_id}, {"$set": {"quota": user["quota"]}})
    ai_text=""
    temp_key=""
    if quota_exceeded == False:
        # --- Génération texte via LLMAPI ---
        payload = {
            "model": "claude-3-haiku",  # mettre le nom exact depuis LLMAPI
            "messages": [
                {"role": "system", "content": system_input},
                {"role": "user", "content": player_input}
            ],
            "temperature": 0.8,
            "max_tokens": 150
        }
        
        headers = {
            "Authorization": f"Bearer {LLMAPI_KEY}",
            "Content-Type": "application/json"
        }
        
        response = requests.post("https://api.llmapi.ai/v1/chat/completions", headers=headers, json=payload)
        result = response.json()
        print(LLMAPI_KEY)
        print(result)
        try:
            ai_text = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            ai_text = "Erreur génération LLMAPI"
        temp_key = generate_temp_token()
    
    return {
        "status": "ok",
        "remaining": user["quota"],
        "quota_exceeded": quota_exceeded,
        "key": temp_key,
        "reply": ai_text
    }

@router.get("/remain")
async def get_quota(patreon_id: str):
    user = users.find_one({"patreon_id": patreon_id})
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")
    reset_if_needed(user)
    return {"remaining": user["quota"],"tier": user["tier_name"]}

@router.post("/admin/set_quota")
async def set_quota(google_id: str, new_quota: int, authorization: str = Header(None)):
    if authorization != f"Bearer {os.getenv('ADMIN_SECRET')}":
        raise HTTPException(status_code=401, detail="unauthorized")

    result = users.update_one({"patreon_id": google_id}, {"$set": {"quota": new_quota}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="user_not_found")

    return {"message": "quota_updated", "patreon_id": google_id, "new_quota": new_quota}

SECRET = os.getenv("SERVER_SECRET")
def generate_temp_token():
    if not SECRET:
        raise RuntimeError("SERVER_SECRET not set")
    unity_key = os.getenv("UNITY_API_KEY")
    if not unity_key:
        raise RuntimeError("UNITY_API_KEY not set")

    exp = datetime.utcnow() + timedelta(seconds=60)
    payload = {
        "key": unity_key,
        "iat": datetime.utcnow(),
        "exp": exp
    }
    token = jwt.encode(payload, SECRET, algorithm="HS256")

    # PyJWT < 2 may return bytes — convert to str if needed
    if isinstance(token, bytes):
        token = token.decode("utf-8")

    return token











































