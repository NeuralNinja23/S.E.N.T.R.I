import os
from dotenv import load_dotenv
from google.genai import types

load_dotenv()

PROJECT_ID = os.getenv("VERTEX_PROJECT_ID")
REGION = os.getenv("VERTEX_REGION", "us-central1")
MODEL = "gemini-live-2.5-flash-native-audio"

# V2 Conversation Configurations
CONVERSATION_ENGINE = "miniomni2"

# MiniOmni2 Model Runtime Configurations
MINIOMNI_HOME = os.getenv("MINIOMNI_HOME", "C:\\Users\\JARVIS\\Desktop\\GenxAI Labz\\MiniOmni 2")
MINIOMNI_SERVER = os.getenv("MINIOMNI_SERVER", "http://127.0.0.1")
MINIOMNI_PORT = int(os.getenv("MINIOMNI_PORT", "60808"))
MINIOMNI_PYTHON = os.getenv("MINIOMNI_PYTHON", "venv\\Scripts\\python.exe")

# Database Settings
from pathlib import Path
DATABASE_PATH = os.getenv(
    "SENTINEL_DATABASE_PATH",
    str(Path(__file__).resolve().parent.parent / "Sentinel.db")
)

# Vision Settings
VISION_INTERVAL = 2.0  # seconds between screen captures
VISION_MIN_DIFF = 50.0 # minimum MSE difference to trigger an upload

# Standby Settings
STANDBY_TIMEOUT_SECONDS = 900  # 15 minutes of inactivity before auto-standby


# FIX #44: Fix typo in instruction path ("Instrctions" -> "Sentinel/Instructions")
instruction_path = Path(__file__).parent / "Sentinel" / "Instructions" / "sentinel.md"
try:
    with open(instruction_path, "r", encoding="utf-8") as f:
        SENTINEL_SYSTEM_INSTRUCTION = f.read()
except FileNotFoundError:
    SENTINEL_SYSTEM_INSTRUCTION = "You are SENTINEL"

import platform

def get_os() -> str:
    return platform.system()

def is_windows() -> bool:
    return get_os() == "Windows"

def is_mac() -> bool:
    return get_os() == "Darwin"

def is_linux() -> bool:
    return get_os() == "Linux"

SENTINEL_PROMPT = types.Content(
    role="system",
    parts=[types.Part.from_text(text=SENTINEL_SYSTEM_INSTRUCTION)]
)
