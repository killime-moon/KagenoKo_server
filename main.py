import os
import requests
from fastapi import FastAPI
from routes import auth, quota
from routes import auth_patreon_web

app = FastAPI()
app.include_router(auth.router, prefix="/api/auth")
app.include_router(quota.router, prefix="/api/quota")
app.include_router(auth_patreon_web.router, prefix="/api/auth/patreon")

PATREON_CLIENT_ID = os.getenv("PATREON_CLIENT_ID")
PATREON_CLIENT_SECRET = os.getenv("PATREON_CLIENT_SECRET")

def get_creator_access_token():
    response = requests.post(
        "https://www.patreon.com/api/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_id": PATREON_CLIENT_ID,
            "client_secret": PATREON_CLIENT_SECRET,
        }
    )
    if response.status_code != 200:
        print(f"[Patreon] Impossible d'obtenir le token : {response.status_code} {response.text}")
        return None
    return response.json().get("access_token")

def fetch_and_display_tiers():
    token = get_creator_access_token()
    if not token:
        return
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    response = requests.get(
        "https://www.patreon.com/api/oauth2/v2/campaigns",
        headers=headers,
        params={
            "include": "tiers",
            "fields[tier]": "title,amount_cents,patron_count,published",
            "fields[campaign]": "summary,patron_count"
        }
    )

    if response.status_code != 200:
        print(f"[Patreon] Erreur lors de la récupération des abonnements : {response.status_code}")
        print(response.text)
        return

    data = response.json()
    tiers = [item for item in data.get("included", []) if item["type"] == "tier"]

    if not tiers:
        print("[Patreon] Aucun abonnement trouvé.")
        return

    print("[Patreon] ── Abonnements disponibles ──────────────────────")
    for tier in tiers:
        attrs = tier["attributes"]
        if not attrs.get("published", False):
            continue
        title = attrs.get("title", "Sans titre")
        amount = attrs.get("amount_cents", 0) / 100
        patrons = attrs.get("patron_count", 0)
        tier_id = tier["id"]
        print(f"  • [{tier_id}] {title} — {amount:.2f} € ({patrons} abonnés)")
    print("[Patreon] ─────────────────────────────────────────────────")

fetch_and_display_tiers()

@app.get("/")
def home():
    return {"message": "Unity AI Server is running!"}
