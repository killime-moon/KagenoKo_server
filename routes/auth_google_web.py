from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
import os
import requests
from urllib.parse import urlencode
from database import users
from models import create_user
import time
import threading

router = APIRouter()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = "https://concerned-amalea-moonlab-072e772d.koyeb.app/api/auth/google/callback"

# Mémoire temporaire : { session_key: {"google_id": str, "timestamp": float} }
temp_sessions = {}

# 🧹 Nettoyage automatique (toutes les 30 secondes)
def cleanup_temp_sessions():
    while True:
        now = time.time()
        expired = [key for key, data in temp_sessions.items() if now - data["timestamp"] > 10]
        for key in expired:
            temp_sessions.pop(key, None)
        time.sleep(30)

threading.Thread(target=cleanup_temp_sessions, daemon=True).start()


# ------------------------
# 1️⃣ Lien de connexion depuis Unity
# ------------------------
@router.get("/web_login")
async def web_login(session_key: str):
    """
    Unity appelle cette route avec un paramètre session_key unique.
    Ex: /api/auth/google/web_login?session_key=XXXX
    """

    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
        "state": session_key,  # 🔹 On garde la clé Unity pour la retrouver plus tard
    }

    url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return RedirectResponse(url)


# ------------------------
# 2️⃣ Callback Google → récupère le token
# ------------------------
@router.get("/callback")
async def google_callback(request: Request):
    code = request.query_params.get("code")
    session_key = request.query_params.get("state")  # 🔹 récupéré automatiquement

    if not code:
        raise HTTPException(status_code=400, detail="missing_code")

    # Étape 1 : échange le code contre un token
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code"
    }

    token_res = requests.post(token_url, data=data)
    token_json = token_res.json()

    if "id_token" not in token_json:
        return JSONResponse(status_code=400, content={"error": "no_id_token", "google_response": token_json})

    # Étape 2 : récupère les infos utilisateur
    id_token_data = requests.get(
        f"https://oauth2.googleapis.com/tokeninfo?id_token={token_json['id_token']}"
    ).json()

    google_id = id_token_data.get("sub")
    email = id_token_data.get("email")

    if not google_id or not email:
        raise HTTPException(status_code=400, detail="invalid_token_data")

    # Étape 3 : crée l’utilisateur si besoin
    user = users.find_one({"google_id": google_id})
    if not user:
        user = create_user(google_id, email)
        users.insert_one(user)

    # Étape 4 : stocke la session temporaire
    temp_sessions[session_key] = {"google_id": google_id, "timestamp": time.time()}

    # Étape 5 : redirige vers la page /success
    return RedirectResponse(f"https://concerned-amalea-moonlab-072e772d.koyeb.app/api/auth/google/success?session_key={session_key}")


# ------------------------
# 3️⃣ Page de succès (affichée à l’utilisateur)
# ------------------------
@router.get("/success")
async def login_success(session_key: str):
    html_content = f"""
    <html>
    <head>
        <title>Connexion réussie</title>
        <style>
            body {{
                background-color: #0e0e0e;
                color: white;
                font-family: Arial, sans-serif;
                text-align: center;
                padding-top: 100px;
            }}
            .msg {{
                font-size: 20px;
                margin-bottom: 20px;
            }}
        </style>
    </head>
    <body>
        <div class="msg">Connexion réussie 🎉</div>
        <div>(Tu peux fermer cette page et retourner dans le jeu)</div>

        <script>
            // Supprime la page après 10 secondes
            setTimeout(() => {{
                fetch("/api/auth/google/delete_temp/{session_key}", {{ method: "DELETE" }});
            }}, 10000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


# ------------------------
# 4️⃣ Unity vérifie si la connexion est prête
# ------------------------
@router.get("/get_temp/{session_key}")
async def get_temp_session(session_key: str):
    session = temp_sessions.get(session_key)
    if not session:
        return JSONResponse({"error": "Session expirée ou inexistante"})
    return {"google_id": session["google_id"]}


# ------------------------
# 5️⃣ Suppression manuelle (appelée par JS ou le cleanup)
# ------------------------
@router.delete("/delete_temp/{session_key}")
async def delete_temp_session(session_key: str):
    temp_sessions.pop(session_key, None)
    return {"status": "deleted"}

