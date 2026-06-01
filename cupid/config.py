"""Cấu hình cho hệ thống mai mối Cupid."""
import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CHAT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")

PEOPLE_PATH = os.getenv("CUPID_PEOPLE", "cupid/data/people.json")
WAITLIST_PATH = os.getenv("CUPID_WAITLIST", "cupid/data/waitlist.json")

TOP_K = 5                 # số gợi ý trả về
MATCH_THRESHOLD = 0.60    # ngưỡng "đủ hợp" để báo ghép từ hàng đợi
