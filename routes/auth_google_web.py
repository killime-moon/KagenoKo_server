from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
import os, requests
from urllib.parse import urlencode
from database import users
from models import create_user

router = APIRouter()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = "https://kagenoko-server.onrender.com/api/auth/google/callback"

@router.get("/web_login")
async def web_login():
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "prompt": "consent"
    }
    url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return RedirectResponse(url)

@router.get("/callback")
async def google_callback(request: Request):
    code = request.query_params.get("code")
    if not code:
        return {"error": "missing_code"}

    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code"
    }
    token_res = requests.post(token_url, data=data).json()
    id_token_data = requests.get(
        f"https://oauth2.googleapis.com/tokeninfo?id_token={token_res['id_token']}"
    ).json()

    google_id = id_token_data["sub"]
    email = id_token_data["email"]

    # Vérifie si l'utilisateur existe
    user = users.find_one({"google_id": google_id})
    if not user:
        user = create_user(google_id, email)
        users.insert_one(user)

    # Simule un token de session (ici juste google_id)
    session_token = google_id

    # Redirige vers Unity via deep link
    return RedirectResponse(f"unity://login_success?session={session_token}")
