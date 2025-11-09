from datetime import datetime

def create_user(patreon_id: str, email: str):
    return {
        "patreon_id": patreon_id,
        "email": email,
        "quota": 50,
        "last_reset": datetime.utcnow().isoformat()
    }

