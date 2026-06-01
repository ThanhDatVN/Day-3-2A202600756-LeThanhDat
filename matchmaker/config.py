"""Central config for the hard-case ReAct matchmaker."""
import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CHAT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")

# Real Google Sheet (optional). If empty, we read the local CSV that simulates it.
SHEET_ID = os.getenv("SHEET_ID", "")
PROFILES_CSV = os.getenv("MATCHMAKER_CSV", "matchmaker/data/profiles.csv")

# ReAct + matching thresholds
MAX_STEPS = 10            # tool-calling steps per hard case
SIM_THRESHOLD = 0.65      # min similarity to propose a pair
OUTBOX_DIR = "matchmaker/outbox"
RESULTS_PATH = "matchmaker/results.json"
