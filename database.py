from pymongo import MongoClient
import os
from dotenv import load_dotenv
import certifi  # <- on ajoute certifi pour gérer le SSL

load_dotenv()

# On force l'utilisation du certificat CA fourni par certifi
client = MongoClient(os.getenv("MONGO_URI"), tlsCAFile=certifi.where())

db = client["cluster0"]
users = db["users"]

