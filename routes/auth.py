from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from google.oauth2 import id_token
from google.auth.transport import requests
from database import users
from models import create_user
import os
from datetime import datetime

router = APIRouter()

class TokenRequest(BaseModel):
    token: str

@router.post("/google")
async def google_login(payload: TokenRequest):
    token = payload.token

    # --- MODE TEST (pour dev local) ---
    # Envoi "FAUX_TOKEN_TEST" depuis Postman / curl pour recevoir un utilisateur factice.
    if token == "FAUX_TOKEN_TEST":
        google_id = "test-google-123"
        email = "test.user@example.com"

        user = users.find_one({"google_id": google_id})
        if not user:
            # create_user retourne un dict avec fields nécessaires
            new_user = create_user(google_id, email)
            # on s'assure que last_reset existe et est en ISO
            if "last_reset" not in new_user:
                new_user["last_reset"] = datetime.utcnow().isoformat()
            users.insert_one(new_user)
            return {"message": "user_created_test", "google_id": google_id, "quota": new_user["quota"]}

        # si déjà présent
        # (on garde la logique de reset hebdo si tu l'as ailleurs)
        return {"message": "user_exists_test", "google_id": google_id, "quota": user.get("quota", 0)}

    # --- MODE RÉEL : vérification du id_token par Google ---
    try:
        idinfo = id_token.verify_oauth2_token(token, requests.Request(), os.getenv("GOOGLE_CLIENT_ID"))
        google_id = idinfo["sub"]
        email = idinfo.get("email", "")

        user = users.find_one({"google_id": google_id})
        if not user:
            new_user = create_user(google_id, email)
            users.insert_one(new_user)
            return {"message": "user_created", "google_id": google_id, "quota": new_user["quota"]}

        return {"message": "user_exists", "google_id": google_id, "quota": user.get("quota", 0)}

    except Exception as e:
        # retourne l'erreur (utile en dev) ; en prod tu peux renvoyer un message plus générique
        raise HTTPException(status_code=400, detail=str(e))


