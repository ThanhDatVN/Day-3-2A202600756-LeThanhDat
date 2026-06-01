"""
Matchmaking Agent (single-shot, reads the sheet directly).

This is the one agent the demo uses. It does NOT run a multi-step tool loop;
instead it:
  1. Reads profiles straight from the sheet (Matchmaker).
  2. Computes the candidate ranking deterministically (embeddings/offline).
  3. Makes ONE grounded LLM call to phrase the recommendation + reason in Vietnamese.
     If there is no API key, it falls back to a templated answer.

Every call is logged to logs/ with token/latency telemetry.
"""
import os
import re
from typing import Dict, Any, Optional

from src.matchmaking.matcher import Matchmaker
from src.telemetry.logger import logger
from src.telemetry.metrics import tracker

SYSTEM_PROMPT = (
    "Bạn là trợ lý mai mối thông minh. Bạn CHỈ được dùng dữ liệu ứng viên được "
    "cung cấp trong phần DỮ LIỆU, TUYỆT ĐỐI không bịa thêm hồ sơ hay tên không có "
    "trong danh sách. Hãy đề xuất cặp ghép phù hợp nhất và giải thích ngắn gọn lý "
    "do dựa trên sở thích/mong muốn chung. Trả lời bằng tiếng Việt, súc tích."
)


class MatchmakingAgent:
    def __init__(self, matcher: Matchmaker, chat_model: str = "gpt-4o-mini",
                 api_key: Optional[str] = None):
        self.matcher = matcher
        self.chat_model = chat_model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._provider = None  # lazy OpenAIProvider

    # ------------------------------------------------------------------ public
    def answer(self, query: str) -> Dict[str, Any]:
        logger.log_event("MATCH_AGENT_START", {"query": query, "mode": self.matcher.mode})
        target_id = self._detect_target(query)

        if target_id:
            data = self.matcher.find_topk(target_id, k=3)
            grounded = self._format_candidates(data)
        else:
            data = self.matcher.topk_all(k=3)
            grounded = self._format_topk_all(data)

        answer_text = self._phrase(query, grounded)

        logger.log_event("MATCH_AGENT_END", {
            "target": target_id, "mode": self.matcher.mode,
        })
        return {
            "query": query,
            "target": target_id,
            "answer": answer_text,
            "data": data,
            "similarity_mode": self.matcher.mode,
        }

    # --------------------------------------------------------------- intent
    def _detect_target(self, query: str) -> Optional[str]:
        if re.search(r"\b(tất cả|toàn bộ|tat ca|toan bo|all|ghép hết|mọi người)\b",
                     query.lower()):
            return None
        m = re.search(r"\bP\d{1,3}\b", query, re.IGNORECASE)
        if m and self.matcher.get(m.group(0)):
            return m.group(0).upper()
        # Try to match a profile name mentioned in the query.
        for p in self.matcher.profiles:
            if re.search(rf"\b{re.escape(p['NAME'].lower())}\b", query.lower()):
                return p["ID"]
        return None

    # --------------------------------------------------------- grounding text
    @staticmethod
    def _format_candidates(data: Dict[str, Any]) -> str:
        if data.get("error"):
            return data["error"]
        t = data["target"]
        lines = [f"Hồ sơ cần ghép: {t['id']} {t['name']}, {t['gender']}, {t['age']} tuổi, "
                 f"{t['location']} | sở thích: {t['hobbies']}", "Ứng viên (đã xếp hạng):"]
        for c in data["candidates"]:
            lines.append(f"- {c['id']} {c['name']} ({c['gender']}, {c['age']}, "
                         f"{c['location']}) | điểm {c['score']:.2f} | {c['reason']}")
        return "\n".join(lines)

    @staticmethod
    def _format_topk_all(data: Dict[str, Any]) -> str:
        lines = [f"Gợi ý Top-{data['stats']['k']} cho {data['stats']['total_profiles']} hồ sơ:"]
        for r in data["results"]:
            tops = ", ".join(f"{c['name']} ({c['score']:.2f})" for c in r["candidates"])
            lines.append(f"- {r['person']['name']} ({r['person']['id']}) → {tops}")
        return "\n".join(lines)

    # ----------------------------------------------------------- LLM phrasing
    def _phrase(self, query: str, grounded: str) -> str:
        prompt = (f"Câu hỏi của admin: {query}\n\nDỮ LIỆU (đã tính sẵn điểm tương đồng):\n"
                  f"{grounded}\n\nHãy đưa ra đề xuất mai mối và giải thích ngắn gọn.")
        provider = self._get_provider()
        if provider is None:
            # Offline fallback: return the computed data with a short header.
            return "📋 (Chế độ offline – không gọi LLM)\n" + grounded

        try:
            result = provider.generate(prompt, system_prompt=SYSTEM_PROMPT)
            tracker.track_request(
                provider=result.get("provider", "openai"),
                model=self.chat_model,
                usage=result.get("usage", {}),
                latency_ms=result.get("latency_ms", 0),
            )
            return result.get("content", "").strip() or grounded
        except Exception as e:  # noqa: BLE001
            logger.log_event("MATCH_AGENT_LLM_ERROR", {"error": str(e)})
            return "⚠️ Lỗi gọi LLM, hiển thị kết quả tính toán:\n" + grounded

    def _get_provider(self):
        if self._provider is not None:
            return self._provider
        if not self.api_key or re.search(r"x{4,}", self.api_key):
            return None
        try:
            from src.core.openai_provider import OpenAIProvider
            self._provider = OpenAIProvider(model_name=self.chat_model, api_key=self.api_key)
        except Exception:
            self._provider = None
        return self._provider
