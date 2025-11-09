from fastapi import APIRouter, HTTPException, Header
from database import users
from datetime import datetime, timedelta
import os

router = APIRouter()

def reset_if_needed(user):
    last_reset = datetime.fromisoformat(user["last_reset"])
    if datetime.utcnow() - last_reset > timedelta(days=7):
        user["quota"] = 50
        user["last_reset"] = datetime.utcnow().isoformat()
        users.update_one({"patreon": user["google_id"]}, {"$set": user})

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



