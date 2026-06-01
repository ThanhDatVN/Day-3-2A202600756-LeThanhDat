"""
FastAPI cho Cupid — mai mối từ mô tả ngôn ngữ tự nhiên.

Run:
    python -m cupid.app      ->  http://127.0.0.1:8000

Endpoints:
    GET  /              trang demo
    POST /api/match     {text}                 -> hồ sơ trích xuất + top-5 + đánh giá
    POST /api/wait      {profile, rejected[]}   -> lưu vào hàng đợi
    GET  /api/waitlist  danh sách đang chờ
"""
import os
import sys

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from cupid import agent, waitlist

app = FastAPI(title="Cupid AI", version="1.0")
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")


class MatchRequest(BaseModel):
    text: str


class WaitRequest(BaseModel):
    profile: Dict[str, Any]
    rejected: List[str] = []


class AcceptRequest(BaseModel):
    candidate_id: str


@app.get("/", response_class=HTMLResponse)
def index():
    with open(os.path.join(WEB_DIR, "index.html"), "r", encoding="utf-8") as f:
        return f.read()


@app.post("/api/match")
def api_match(req: MatchRequest):
    return JSONResponse(agent.process(req.text))


@app.post("/api/wait")
def api_wait(req: WaitRequest):
    return JSONResponse(agent.reject_and_wait(req.profile, req.rejected))


@app.post("/api/accept")
def api_accept(req: AcceptRequest):
    return JSONResponse(agent.accept(req.candidate_id))


@app.get("/api/waitlist")
def api_waitlist():
    return {"waiting": waitlist.list_all()}


if __name__ == "__main__":
    import uvicorn
    print("Open http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
