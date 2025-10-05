from datetime import datetime

def create_user(google_id: str, email: str):
    return {
        "google_id": google_id,
        "email": email,
        "quota": 50,
        "last_reset": datetime.utcnow().isoformat()
    }
