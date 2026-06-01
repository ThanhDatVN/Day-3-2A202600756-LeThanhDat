"""
FastAPI demo cho Agent Mai Mối (bản nâng cấp 8 tính năng).

Run:
    python app.py   ->  http://127.0.0.1:8000

Endpoints:
    GET  /                 trang demo
    GET  /api/profiles     danh sách hồ sơ (Sheet)
    POST /api/review       AI review dữ liệu trước khi match
    POST /api/match        ghép Top-K cho mọi người (+ export CSV/JSON)
    POST /api/places       gợi ý địa điểm hẹn hò cho 1 cặp {a_id, b_id}
    POST /api/report       tạo Match Report (markdown)
    POST /api/notify       gửi Email + Zalo (outbox) lần lượt
    POST /api/assistant    AI chat assistant cho volunteer {query}
    POST /api/ask          agent gợi ý nhanh {query}
"""
import os
import sys

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from src.matchmaking.matcher import Matchmaker
from src.matchmaking.agent import MatchmakingAgent
from src.matchmaking.assistant import VolunteerAssistant
from src.matchmaking import reviewer, report, notifier, places

app = FastAPI(title="Agent Mai Mối", version="2.0")

CSV_PATH = os.getenv("PROFILES_CSV", "data/profiles.csv")
CHAT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
TOP_K = int(os.getenv("TOP_K", "3"))

matcher = Matchmaker(csv_path=CSV_PATH)
agent = MatchmakingAgent(matcher, chat_model=CHAT_MODEL)
assistant = VolunteerAssistant(matcher, chat_model=CHAT_MODEL)

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")


class AskRequest(BaseModel):
    query: str


class PlacesRequest(BaseModel):
    a_id: str
    b_id: str


@app.get("/", response_class=HTMLResponse)
def index():
    with open(os.path.join(WEB_DIR, "index.html"), "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/profiles")
def api_profiles():
    profiles = [{
        "id": p["ID"], "name": p["NAME"], "age": p["AGE"], "gender": p["GENDER"],
        "location": p["LOCATION"], "hobbies": p["HOBBIES"],
        "looking_for": p["LOOKING_FOR"], "email": p.get("EMAIL", ""), "zalo": p.get("ZALO", ""),
    } for p in matcher.profiles]
    return {"profiles": profiles, "similarity_mode": matcher.mode}


@app.post("/api/review")
def api_review():
    return JSONResponse(reviewer.review(matcher.profiles, chat_model=CHAT_MODEL))


@app.post("/api/match")
def api_match():
    topk = matcher.topk_all(k=TOP_K)
    paths = matcher.export(topk)
    topk["exported"] = paths
    return JSONResponse(topk)


@app.post("/api/places")
def api_places(req: PlacesRequest):
    a = matcher.get(req.a_id)
    b = matcher.get(req.b_id)
    if not a or not b:
        return JSONResponse({"error": "Không tìm thấy hồ sơ."}, status_code=404)
    return JSONResponse(places.suggest_places(
        matcher._brief(a), matcher._brief(b), chat_model=CHAT_MODEL))


@app.post("/api/report")
def api_report():
    topk = matcher.topk_all(k=TOP_K)
    greedy = matcher.greedy_pairs()
    rev = reviewer.review(matcher.profiles, chat_model=CHAT_MODEL)
    return JSONResponse(report.build_report(topk, greedy, rev))


@app.post("/api/notify")
def api_notify():
    topk = matcher.topk_all(k=TOP_K)
    return JSONResponse(notifier.send_all(topk))


@app.post("/api/assistant")
def api_assistant(req: AskRequest):
    return JSONResponse(assistant.ask(req.query))


@app.post("/api/ask")
def api_ask(req: AskRequest):
    return JSONResponse(agent.answer(req.query))


if __name__ == "__main__":
    import uvicorn
    print(f"Open http://127.0.0.1:8000  (similarity mode: {matcher.mode}, top_k={TOP_K})")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
