from datetime import datetime

def create_user(patreon_id: str, email: str, tier_name: str):
    return {
        "patreon_id": patreon_id,
        "email": email,
        "tier_name": tier_name,
        "quota": 50,
        "last_reset": datetime.utcnow().isoformat()
    }


