from flask import Flask, request, jsonify
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

# Données fictives en mémoire (plus tard tu mettras une vraie base)
users = {}

# Chargement du Client ID Google
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

@app.route("/")
def home():
    return "Serveur Unity AI en local ✅"

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email")

    if email not in users:
        # Création d’un nouvel utilisateur avec un quota par défaut
        users[email] = {"quota": 50, "used": 0}

    return jsonify({"message": "Utilisateur connecté", "user": users[email]})

@app.route("/use", methods=["POST"])
def use_quota():
    data = request.json
    email = data.get("email")

    if email not in users:
        return jsonify({"error": "Utilisateur inconnu"}), 400

    user = users[email]
    if user["used"] >= user["quota"]:
        return jsonify({"error": "Quota dépassé"}), 403

    user["used"] += 1
    return jsonify({"message": "Interaction autorisée", "used": user["used"], "quota": user["quota"]})

if __name__ == "__main__":
    app.run(port=8000, debug=True)

