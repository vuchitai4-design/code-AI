from groq import Groq
import os
from dotenv import load_dotenv


load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

client = Groq(api_key=GROQ_API_KEY)
# Danh sách Process Game cần ưu tiên nhường tài nguyên (FO4 và Minecraft Legacy Launcher)

GAME_PROCESSES = [
    "fifazo4.exe",
    "fifazo4zc.exe",
    "ff4.exe",
    "legacy launcher.exe",
    "tlauncher.exe",
    "javaw.exe",  # Runtime Minecraft
]