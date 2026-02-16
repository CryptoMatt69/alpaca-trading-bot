# test_keys.py
from dotenv import load_dotenv
import os

load_dotenv()

print("APCA_API_KEY_ID:", os.environ.get("APCA_API_KEY_ID"))
print("APCA_API_SECRET_KEY:", os.environ.get("APCA_API_SECRET_KEY"))
print("APCA_API_BASE_URL:", os.environ.get("APCA_API_BASE_URL"))

