# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Le Thanh Dat
- **Student ID**: 2A202600756
- **Date**: 2026-06-01

---

## I. Technical Contribution (15 Points)

Tôi xây dựng toàn bộ **Cupid AI** — agent mai mối từ mô tả ngôn ngữ tự nhiên —
theo kiến trúc module hóa, tách rõ "việc của LLM" và "việc của code".

- **Modules Implemented**:
  - `cupid/llm.py` — lớp gọi OpenAI dùng chung (`chat_json` / `chat_text` /
    `embed`) **kèm telemetry**: mọi lời gọi log JSON token + latency
    (`_track`, `log`). Đây là nền cho toàn bộ phân tích ở §II.
  - `cupid/extractor.py` — tool `extract_profile`: NL tự do → 6 trường JSON (JSON
    mode), có chuẩn hóa & default an toàn cho mọi trường.
  - `cupid/compatibility.py` — tool tính điểm **tất định**: lọc cứng khác giới +
    điểm đa tầng (semantic embedding 0.50 / req 0.20 / age 0.12 / address 0.18) +
    `top_k`, và **ẩn SĐT** khỏi payload gợi ý.
  - `cupid/evaluator.py` — tool `evaluate_candidates`: sinh nhãn hợp + nhận xét +
    lời khuyên kết nối cho Top-5.
  - `cupid/waitlist.py` — "database" hàng đợi (JSON) + logic tự ghép khi có người
    mới (`check_new_user`, ngưỡng `MATCH_THRESHOLD`).
  - `cupid/agent.py` — điều phối pipeline (`process` / `accept` / `reject_and_wait`).
  - `cupid/app.py` (FastAPI + `web/index.html`) và `cupid/main.py` (demo terminal).

- **Code Highlights**:
  - Lọc cứng + ẩn PII trong cùng một bước — `compatibility.py:64,79`:
    ```python
    people = [p for p in people if _opposite_gender(user.get("gender"), p.get("gender"))]
    ...
    public = {key: val for key, val in p.items() if key != "phone"}  # ẩn SĐT
    ```
  - Telemetry tự động cho mọi lời gọi — `llm.py:36-41` (`_track` → `LLM_METRIC`).
  - Default an toàn để **degrade gracefully** khi thiếu trường —
    `compatibility.py:48-58` (`age=0.5`, `addr=0.0` khi thiếu dữ liệu).

- **Documentation (tương tác với pipeline ReAct)**: mỗi tool là một *Action* với
  *Observation* rõ ràng; `agent.process` xâu chuỗi `extract → check_waitlist →
  score → evaluate` theo thứ tự tất định, không để LLM tự chọn tool → không loop
  vô hạn, chi phí mỗi task có trần (đo được ở §II).

---

## II. Debugging Case Study (10 Points)

- **Problem Description**: Agent **suy luận sai giới tính người dùng**. Với input
  `"tôi tên hoàng, sinh năm 2003 … tôi muốn tìm bạn nữ cute, lùn"`, tool
  `extract_profile` gán `gender = "Nữ"`. Vì lọc cứng chỉ giữ người **khác giới**,
  Top-5 trả về toàn **nam** — sai hoàn toàn mục tiêu của một người dùng nam.

- **Log Source** (`logs/cupid-2026-06-01.log`, `10:28:45`):
  ```json
  {"event":"EXTRACT","data":{"input":"tôi tên hoàng, sinh năm 2003 ... tìm bạn nữ cute, lùn",
   "profile":{"name":"hoàng","age":20,"gender":"Nữ", ...}}}
  ```
  So với lần ngay sau đó (`10:29:15`) khi tôi thêm `"giới tính nam"`:
  ```json
  {"event":"EXTRACT","data":{"profile":{"name":"Hoàng","age":20,"gender":"Nam", ...}}}
  ```

- **Diagnosis**: Đây là lỗi **prompt/spec**, không phải lỗi model hay tool. System
  prompt mô tả `gender` là "suy ra" nhưng **không phân biệt** giới tính *người
  nói* với giới tính *đối phương mong muốn*. Cụm "tìm bạn **nữ**" bị LLM hiểu là
  giới tính người nói. Thiếu **few-shot** cho lớp input dễ nhầm này.
  - *Phát hiện phụ trong cùng log*: `"sinh năm 2003" → age 20` trong khi ngày chạy
    là **2026** (đúng phải 23, lệch **−3 năm nhất quán**, kể cả `1999→24`). Root
    cause: LLM không biết ngày hiện tại → tính số học sai có hệ thống.

- **Solution**:
  1. *Đã kiểm chứng bằng dữ liệu*: input nêu rõ giới tính → `extract` trả đúng
     (bằng chứng 2 dòng log trên).
  2. *Bản vá prompt (v2)*: thêm luật *"`gender` là giới tính NGƯỜI MÔ TẢ; câu 'tìm
     bạn nữ/nam' là yêu cầu đối phương, KHÔNG dùng để suy giới tính người nói"* +
     1 few-shot — ablation trong báo cáo nhóm §5 Experiment 1.
  3. *Bài học kiến trúc*: **không giao số học cho LLM** — trích `birth_year` rồi
     để code tính `age = current_year - birth_year`, loại bỏ lỗi −3 năm tận gốc.

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

1. **Reasoning**: Việc tách thành các bước có *Observation* (tương đương khối
   `Thought`) giúp tôi **chèn ràng buộc cứng giữa các bước** mà một chatbot trả
   lời thẳng không làm được: sau khi `extract` ra `gender`, code **bắt buộc** lọc
   khác giới trước khi tính điểm. Chatbot gộp mọi thứ trong một lượt sinh chữ nên
   hay "quên" ràng buộc và bịa điểm số. Lập luận của agent **kiểm chứng được**
   vì điểm số đến từ code, không từ văn bản LLM.

2. **Reliability**: Agent **kém hơn** chatbot ở các tình huống **hội thoại mở /
   ngoài kịch bản** — ví dụ người dùng hỏi xã giao hay nhập mô tả quá nghèo ngữ
   cảnh (case "Thành" thiếu địa chỉ & sở thích, log `10:38`): pipeline cứng vẫn
   chạy nhưng trả kết quả nhạt, trong khi chatbot sẽ tự nhiên hỏi lại. Agent tối
   ưu cho **tác vụ có cấu trúc**, không cho tán gẫu.

3. **Observation**: Phản hồi môi trường định hình bước kế tiếp rất rõ ở **hàng
   đợi**: khi user mới (Tuấn) vào, *observation* từ `check_waitlist` = "Trang đang
   chờ, điểm ≥ 0.60" đã **kích hoạt một nhánh hành động khác** (tự báo ghép, rời
   hàng đợi — log `WAITLIST_MATCH 10:08:35`). Không có vòng quan sát này, một
   chatbot one-shot không thể "nhớ" Trang để ghép về sau.

---

## IV. Future Improvements (5 Points)

- **Scalability (RAG)**: thay JSON file 30 hồ sơ bằng **vector DB (pgvector /
  Pinecone)**; **cache embedding hồ sơ** thay vì re-embed mỗi request (hiện mỗi
  task embed lại toàn bộ — tối ưu latency/cost lớn nhất); lọc Top-K bằng ANN để
  chạy ở quy mô vạn hồ sơ.
- **Safety**: thêm **Supervisor LLM** audit output `extract` (chống prompt
  injection vào mô tả), schema-validate nghiêm, và **clarify loop** hỏi lại khi
  thiếu trường quan trọng.
- **Performance / Reliability**: thêm **backup provider** (Gemini Flash) khi
  OpenAI lỗi; rút gọn `evaluate` (bước chậm nhất ~6s) bằng cách chỉ sinh lời
  khuyên cho người được chọn thay vì cả Top-5; stream kết quả để giảm
  time-to-first-token.

---

> [!NOTE]
> Bản nộp cá nhân: `REPORT_LeThanhDat.md` trong `report/individual_reports/`.
