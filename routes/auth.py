from fastapi import APIRouter, HTTPException
from google.oauth2 import id_token
from google.auth.transport import requests
from database import users
from models import create_user
import os

router = APIRouter()

@router.post("/google")
async def google_login(token: str):
    try:
        idinfo = id_token.verify_oauth2_token(token, requests.Request(), os.getenv("GOOGLE_CLIENT_ID"))
        google_id = idinfo["sub"]
        email = idinfo["email"]

        user = users.find_one({"google_id": google_id})
        if not user:
            new_user = create_user(google_id, email)
            users.insert_one(new_user)
            return {"message": "user_created", "quota": 50}

        return {"message": "user_exists", "quota": user["quota"]}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
