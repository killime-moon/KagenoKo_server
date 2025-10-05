from fastapi import FastAPI
from routes import auth, quota

app = FastAPI()

app.include_router(auth.router, prefix="/api/auth")
app.include_router(quota.router, prefix="/api/quota")

@app.get("/")
def home():
    return {"message": "Unity AI Server is running!"}
