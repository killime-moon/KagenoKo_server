from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
import os
import requests
from urllib.parse import urlencode
from database import users
from models import create_user
from fastapi.responses import HTMLResponse

router = APIRouter()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = "https://kagenoko-server.onrender.com/api/auth/google/callback"

# ------------------------
# 1️⃣ Lien de connexion
# ------------------------
@router.get("/web_login")
async def web_login():
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",  # permet d'obtenir un refresh_token
        "prompt": "consent"       # force le choix du compte
    }
    url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return RedirectResponse(url)

# ------------------------
# 2️⃣ Callback après login
# ------------------------
@router.get("/callback")
async def google_callback(request: Request):
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="missing_code")

    # Étape 1 : Échange le code contre un token
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

    # Vérifie si Google a bien renvoyé l'id_token
    if "id_token" not in token_json:
        return JSONResponse(
            status_code=400,
            content={"error": "no_id_token_returned", "google_response": token_json}
        )

    # Étape 2 : Vérifie le token et récupère l'info utilisateur
    id_token_data = requests.get(
        f"https://oauth2.googleapis.com/tokeninfo?id_token={token_json['id_token']}"
    ).json()

    google_id = id_token_data.get("sub")
    email = id_token_data.get("email")

    if not google_id or not email:
        raise HTTPException(status_code=400, detail="invalid_token_data")

    # Étape 3 : Vérifie ou crée l’utilisateur
    user = users.find_one({"google_id": google_id})
    if not user:
        user = create_user(google_id, email)
        users.insert_one(user)

    # Étape 4 : Renvoie un “token” (ici, juste google_id)
    session_token = google_id

    # Étape 5 : Redirige vers Unity
    # Pour les tests, on peut aussi rediriger vers une page web simple :
    # return RedirectResponse(f"https://yourwebsite.com/success?session={session_token}")
    return RedirectResponse(f"https://kagenoko-server.onrender.com/api/auth/google/success?session={session_token}")

@router.get("/success")
async def login_success(session: str):
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
            const id = '{session}';
            localStorage.setItem('google_id', id);
            const blob = new Blob([id], {{type: 'text/plain'}});
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = 'google_id.txt';
            link.click();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


