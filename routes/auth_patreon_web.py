from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
import os
import requests
import time
import threading
from urllib.parse import urlencode
from database import users
from models import create_user
from datetime import datetime, timedelta

router = APIRouter()

PATREON_CLIENT_ID = os.getenv("PATREON_CLIENT_ID")
PATREON_CLIENT_SECRET = os.getenv("PATREON_CLIENT_SECRET")
REDIRECT_URI = "https://concerned-amalea-moonlab-072e772d.koyeb.app/api/auth/patreon/callback"

temp_sessions = {}

# Nettoyage périodique
def cleanup_temp_sessions():
    while True:
        now = time.time()
        expired = [k for k, v in temp_sessions.items() if now - v["timestamp"] > 10]
        for k in expired:
            temp_sessions.pop(k, None)
        time.sleep(30)

threading.Thread(target=cleanup_temp_sessions, daemon=True).start()

# --------------------------------------------------
# 1️⃣ Démarre la connexion Patreon
# --------------------------------------------------
@router.get("/web_login")
async def patreon_web_login(session_key: str):
    params = {
        "response_type": "code",
        "client_id": PATREON_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": "identity identity[email] identity.memberships",
        "state": session_key,
    }
    url = f"https://www.patreon.com/oauth2/authorize?{urlencode(params)}"
    return RedirectResponse(url)

# --------------------------------------------------
# 2️⃣ Callback OAuth Patreon
# --------------------------------------------------
@router.get("/callback")
async def patreon_callback(request: Request):
    now = datetime.utcnow().isoformat()
    code = request.query_params.get("code")
    session_key = request.query_params.get("state")

    if not code:
        raise HTTPException(status_code=400, detail="missing_code")

    # Échange code ↔ token
    token_url = "https://www.patreon.com/api/oauth2/token"
    data = {
        "code": code,
        "grant_type": "authorization_code",
        "client_id": PATREON_CLIENT_ID,
        "client_secret": PATREON_CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
    }

    res = requests.post(token_url, data=data)
    token_data = res.json()

    if "access_token" not in token_data:
        raise HTTPException(status_code=400, detail=f"token_error: {token_data}")

    access_token = token_data["access_token"]

    # Étape 2 : récupère infos utilisateur + membership
    user_res = requests.get(
        "https://www.patreon.com/api/oauth2/v2/identity",
        headers={"Authorization": f"Bearer {access_token}"},
        params={
            "include": "memberships.currently_entitled_tiers",
            "fields[member]": "patron_status,currently_entitled_amount_cents",
            "fields[tier]": "title,amount_cents",
            "fields[user]": "email,full_name"
        }
    )
    user_json = user_res.json()

    patreon_id = user_json["data"]["id"]
    email = user_json["data"]["attributes"].get("email", "unknown@example.com")

    # --- Détermine le tier Patreon ---
    included = user_json.get("included", [])
    tier_name = "aucun"
    for item in included:
        if item.get("type") == "tier":
            attrs = item.get("attributes", {})
            tier_name = attrs.get("title", "aucun").lower()
            break
    # --- Attribution du quota selon le titre du tier ---
    if "unlimited" in tier_name:
        quota = 5000
    elif "premium" in tier_name:
        quota = 500
    else:
        quota = 50
    # Création / mise à jour utilisateur
    user = users.find_one({"patreon_id": patreon_id})
    if not user:
        new_user = create_user(patreon_id, email, tier_name)
        new_user["quota"] = quota
        new_user["access_token"] = access_token
        new_user["last_reset"] = now
        users.insert_one(new_user)
    else:
        users.update_one({"patreon_id": patreon_id}, {"$set": {"quota": quota}})

    # Stocke session temporaire pour Unity
    temp_sessions[session_key] = {"patreon_id": patreon_id, "timestamp": time.time()}

    # Redirige vers page succès
    return RedirectResponse(
        f"https://concerned-amalea-moonlab-072e772d.koyeb.app/api/auth/patreon/success?session_key={session_key}"
    )

# --------------------------------------------------
# 3️⃣ Page de succès
# --------------------------------------------------
@router.get("/success")
async def success(session_key: str):
    html = f"""
    <html>
    <head>
        <title>Connexion Patreon réussie</title>
        <style>
            body {{
                background-color: #0e0e0e;
                color: white;
                font-family: Arial;
                text-align: center;
                padding-top: 100px;
            }}
        </style>
    </head>
    <body>
        <h2>Connexion réussie via Patreon 🎉</h2>
        <p>(Tu peux fermer cette page et retourner dans le jeu)</p>
        <script>
            setTimeout(() => {{
                fetch("/api/auth/patreon/delete_temp/{session_key}", {{ method: "DELETE" }});
            }}, 10000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(html)

# --------------------------------------------------
# 4️⃣ Unity récupère le patreon_id
# --------------------------------------------------
@router.get("/get_temp/{session_key}")
async def get_temp_session(session_key: str):
    session = temp_sessions.get(session_key)
    if not session:
        return JSONResponse({"error": "Session expirée ou inexistante"})
    return {"patreon_id": session["patreon_id"]}

# --------------------------------------------------
# 5️⃣ Suppression manuelle
# --------------------------------------------------
@router.delete("/delete_temp/{session_key}")
async def delete_temp(session_key: str):
    temp_sessions.pop(session_key, None)
    return {"status": "deleted"}
