import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

# V2 Conversation Engine selection
CONVERSATION_ENGINE = os.getenv("CONVERSATION_ENGINE", "decoupled_pipeline")

# Decoupled Streaming Speech Pipeline Configurations
PIPELINE_PROVIDER = os.getenv("PIPELINE_PROVIDER", "streaming_pipeline")
ASR_PROVIDER = os.getenv("ASR_PROVIDER", "faster_whisper")
REASONING_PROVIDER = os.getenv("REASONING_PROVIDER", "ollama")
REASONING_MODEL = os.getenv("REASONING_MODEL", "phi4-mini:latest")
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "kokoro")
TTS_SPEAKER_VOICE = os.getenv("TTS_SPEAKER_VOICE", "bm_george")

# Language Settings (Bug #10 + Bug #24: configurable instead of hardcoded)
ASR_LANGUAGE = os.getenv("ASR_LANGUAGE", "en")  # Language code for Faster-Whisper ASR
TTS_LANGUAGE = os.getenv("TTS_LANGUAGE", "en-us")  # Language code for Kokoro TTS


# Vision Settings
VISION_INTERVAL = 2.0  # seconds between screen captures
VISION_MIN_DIFF = 50.0  # minimum MSE difference to trigger an upload

# Standby Settings
STANDBY_TIMEOUT_SECONDS = 900  # 15 minutes of inactivity before auto-standby

# Memory Database Configuration
MEMORY_DB_PATH = os.getenv(
    "MEMORY_DB_PATH",
    str(Path(__file__).resolve().parent / "Sentri" / "storage" / "sentri_memory.db"),
)


# System Instruction Template Loader
def get_system_instruction() -> str:
    instruction_path = Path(__file__).parent / "Sentri" / "Instructions" / "sentri.md"
    try:
        with open(instruction_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "You are SENTRI, a highly sophisticated digital assistant."


import platform


def get_os() -> str:
    return platform.system()


def is_windows() -> bool:
    return get_os() == "Windows"


def is_mac() -> bool:
    return get_os() == "Darwin"


def is_linux() -> bool:
    return get_os() == "Linux"
