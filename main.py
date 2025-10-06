from fastapi import FastAPI
from routes import auth, quota
from routes import auth_google_web

app = FastAPI()

app.include_router(auth.router, prefix="/api/auth")
app.include_router(quota.router, prefix="/api/quota")
app.include_router(auth_google_web.router, prefix="/api/auth/google")

@app.get("/")
def home():
    return {"message": "Unity AI Server is running!"}

