# Group Report: Lab 3 - Production-Grade Agentic System

- **Team Name**: Cupid AI 
- **Team Members**: 2A202600582 - Thân Văn Hoàng
                    2A202600756 - Lê Thành Đạt
                    2A202600742 - Nguyễn Văn Hoàng
- **Deployment Date**: 2026-06-01

> **Sản phẩm**: Agent mai mối từ **mô tả ngôn ngữ tự nhiên**. Người dùng tả bản
> thân bằng lời → AI tự trích xuất hồ sơ có cấu trúc → tính độ hợp → gợi ý Top-5
> kèm lời khuyên → người dùng đồng ý (nhận SĐT) hoặc vào **hàng đợi** chờ người
> phù hợp tiếp theo.

---

## 1. Executive Summary

Người đăng ký hẹn hò qua Google Form mô tả bản thân bằng **văn nói tự do**, mỗi
người một kiểu. Ghép tay tốn công, so khớp "word-by-word" kém chính xác. **Cupid
AI** giải quyết bằng một agentic pipeline: mô tả tự nhiên → chuẩn hóa thành dữ
liệu có cấu trúc → tính tương thích đa tầng (có embedding ngữ nghĩa) → gợi ý người
phù hợp + lời khuyên kết nối, và xử lý cả tình huống "chưa ưng ai" bằng hàng đợi.

- **Test set**: 12 mô tả tự nhiên có thật (log `logs/cupid-2026-06-01.log`),
  tiếng Việt có dấu / không dấu, có cả input nhiễu (ngày sinh thay vì tuổi, yêu
  cầu mơ hồ, thiếu giới tính).
- **Success Rate (trích xuất + lọc cứng)**:
  - Trích xuất đủ trường cốt lõi (name/hobbies/requirements): **12/12 = 100%**.
  - Lọc cứng khác giới trên Top-5: **100%** — mọi gợi ý đều đúng giới (không ca
    nào lọt người cùng giới).
  - Suy luận giới tính khi người dùng **không** nói rõ: **1/2 sai** (xem RCA §4).
  - Tính tuổi từ "sinh năm YYYY": **sai hệ thống ~3 năm** (xem RCA §4).
- **Key Outcome so với chatbot baseline**: Baseline (chatbot thuần) khi được dán
  cả 30 hồ sơ và hỏi "tìm người hợp" thường (a) **làm lộ SĐT** ngay trong câu trả
  lời, (b) **không lọc cứng giới tính**, (c) **bịa điểm số** không có cơ sở, và
  (d) **không xử lý** được kịch bản "chưa ưng ai → chờ". Agent loại bỏ cả 4 lỗi
  này nhờ tách bước (tool) và đưa việc tính điểm cho **code tất định** thay vì
  LLM. Trong demo hàng đợi, agent tự động ghép **Trang → Tuấn (đúng 1 lượt)** —
  việc baseline không có cơ chế nào để làm.

---

## 2. System Architecture & Tooling

### 2.1 ReAct Loop Implementation

Agent không dùng vòng lặp ReAct mở (LLM tự chọn tool vô hạn) mà dùng **pipeline
Thought→Action→Observation tất định** — an toàn hơn cho production (không có nguy
cơ loop vô hạn, chi phí dự đoán được). Mỗi bước là một Action có Observation rõ
ràng:

```
   Người dùng nhập MÔ TẢ TỰ NHIÊN
   "Mình là Hùng, 29t, nam, Hà Nội, thích trekking… tìm cô gái yêu thiên nhiên"
                       │
   ① ACTION extract_profile (LLM, JSON mode)
      OBS → {name, age, gender, address, hobbies, requirements}
                       │
   ② ACTION check_waitlist (DB tool)
      OBS → có ai đang chờ mà hợp với người mới này không?
                       │
   ③ ACTION score_candidates (code: embedding + hàm)
      OBS → lọc cứng KHÁC GIỚI → điểm đa tầng (semantic+req+age+addr)
                       │
   ④ filter Top-5 điểm cao nhất (KHÔNG kèm SĐT)
                       │
   ⑤ ACTION evaluate_candidates (LLM, JSON mode)
      OBS → mỗi người: nhãn hợp + nhận xét + lời khuyên bắt chuyện
                       │
   ⑥ Final Answer → giao diện hiển thị Top-5
                       │
        ┌──────────────┴───────────────┐
        ▼                              ▼
   ⑦a ACTION accept(id)          ⑦b ACTION add_to_waitlist
      OBS → trả về SĐT để liên hệ    OBS → lưu hồ sơ + chờ người mới hợp gu
```

**Tóm tắt 1 dòng:** *Mô tả tự nhiên → trích xuất → tính điểm (code) → Top-5 → AI
đánh giá → đồng ý (nhận SĐT) hoặc vào hàng đợi.*

### 2.2 Tool Definitions (Inventory)

| Tool Name | Input Format | Loại | Use Case |
| :--- | :--- | :--- | :--- |
| `extract_profile` | `string → json` | LLM (gpt-4o-mini, JSON mode) | NL tự do → 6 trường có cấu trúc (`extractor.py`) |
| `check_waitlist` | `profile json` | DB (JSON file) | Tìm người đang chờ hợp với user mới, ghép & rời hàng đợi (`waitlist.py`) |
| `score_candidates` | `profile + people[]` | Code tất định + embeddings | Lọc cứng khác giới + điểm đa tầng → Top-5, **ẩn SĐT** (`compatibility.py`) |
| `evaluate_candidates` | `json → json` | LLM (gpt-4o-mini, JSON mode) | Sinh nhãn hợp + nhận xét + lời khuyên kết nối (`evaluator.py`) |
| `accept` | `candidate_id` | DB | **Lộ SĐT** chỉ khi người dùng đồng ý (`agent.py`) |
| `add_to_waitlist` | `profile + rejected[]` | DB | Lưu người chưa ưng ai vào hàng đợi (`waitlist.py`) |

→ **6 tool** (≥ 2 theo yêu cầu), trong đó 2 LLM-tool và 4 code/DB-tool. Việc đẩy
phần **tính điểm sang code tất định** thay vì để LLM tự chấm là quyết định kiến
trúc cốt lõi: điểm số có thể kiểm chứng, không bịa, không phụ thuộc tâm trạng LLM.

### 2.3 LLM Providers Used

- **Primary (chat / trích xuất / đánh giá)**: OpenAI `gpt-4o-mini` (JSON mode).
- **Embeddings (tính tương thích ngữ nghĩa)**: OpenAI `text-embedding-3-small`.
- **Secondary (Backup)**: *chưa cấu hình* — đã ghi nhận là khoảng trống production
  (xem §6); model/endpoint khai báo qua `.env` nên có thể đổi nhà cung cấp mà
  không sửa code.

---

## 3. Telemetry & Performance Dashboard

Mọi lời gọi LLM/embedding được log JSON (token + latency) trong `logs/` bởi
`llm.py::_track`. Số liệu dưới đây parse trực tiếp từ `logs/cupid-2026-06-01.log`
(**12 task hoàn chỉnh = 12 lần `extract` + 12 lần `evaluate` + 14 lần `embed`**).

### Latency (chat gpt-4o-mini, 24 lời gọi)

| Metric | Giá trị |
| :--- | :--- |
| **Average Latency** | **4,496 ms** |
| **P50** | 4,682 ms |
| **P99** | 7,814 ms |
| **Min / Max** | 1,522 ms / 7,814 ms |
| Trung bình bước `extract` | 2,934 ms |
| Trung bình bước `evaluate` | 6,059 ms |
| Trung bình bước `embed` | 956 ms |
| **End-to-end / task** (extract+embed+evaluate) | ≈ **9.9 s** |

> Quan sát: `evaluate` chậm gấp đôi `extract` do completion dài hơn (sinh nhận xét
> + lời khuyên cho 5 người). Đây là điểm tối ưu rõ nhất (xem §6).

### Tokens & Cost

| Metric | Giá trị |
| :--- | :--- |
| **Average Tokens per Task** (2 lời gọi chat) | **≈ 1,147 tokens** |
| — `extract` trung bình | 297 tokens |
| — `evaluate` trung bình | 850 tokens |
| Tổng prompt / completion (24 chat call) | 8,349 / 5,416 tokens |
| Tổng token toàn test suite | 13,765 tokens |
| **Total Cost of Test Suite** (chat) | **≈ $0.0045** (gpt-4o-mini $0.15/$0.60 per 1M) |
| Cost / task | ≈ $0.00037 (embeddings không đáng kể) |

**Token ratio (completion/prompt) ≈ 0.65** — agent gần như không "tán gẫu" thừa
trước khi gọi tool nhờ JSON mode ép định dạng.

---

## 4. Root Cause Analysis (RCA) — Failure Traces

### Case Study 1: Hallucinated Gender (suy luận sai giới tính)

- **Input**: `"tôi tên hoàng, sinh năm 2003 … tôi muốn tìm bạn nữ cute, lùn"`
- **Observation** (log `10:28:45`): `extract` trả `"gender": "Nữ"` — **SAI**. Người
  dùng là **Nam**, "nữ" trong câu là **mong muốn về đối phương**, không phải giới
  tính bản thân.
- **Hậu quả**: lọc cứng khác giới đảo ngược → Top-5 toàn **nam**, sai hoàn toàn.
- **Root Cause**: System prompt của `extractor.py` mô tả trường `gender` là "suy
  ra" nhưng **không phân biệt** "giới tính NGƯỜI NÓI" với "giới tính đối phương
  mong muốn", và **không có few-shot** cho trường hợp dễ nhầm này.
- **Khắc phục đã kiểm chứng**: khi người dùng thêm rõ `"giới tính nam"` (log
  `10:29:15`), `extract` trả đúng `"gender": "Nam"`. → Bản vá đề xuất: thêm vào
  prompt câu *"`gender` là giới tính của NGƯỜI MÔ TẢ; câu 'tìm bạn nữ/nam' là yêu
  cầu đối phương, KHÔNG dùng để suy giới tính người nói"* + 1 few-shot. (Xem
  ablation §5, Experiment 1.)

### Case Study 2: Wrong Tool Output — tính tuổi từ năm sinh

- **Input**: `"… sinh năm 2003 …"` → **Observation**: `"age": 20`. Ngày chạy là
  **2026-06-01** nên tuổi đúng phải là **23** (lệch −3). Tương tự `"sinh năm 1999"`
  → `age: 24` (đúng phải 27, cũng lệch −3).
- **Root Cause**: LLM **không biết ngày hiện tại**, quy chiếu theo "năm nội tại"
  (~2023) trong trọng số huấn luyện → sai hệ thống và **nhất quán −3 năm**.
- **Khắc phục đề xuất**: KHÔNG để LLM tính tuổi. Trích `birth_year` rồi để **code
  tất định** tính `age = current_year - birth_year` (current_year tiêm từ
  `config`). Đây đúng tinh thần "việc số học giao cho code, không giao cho LLM".

### Case Study 3: Empty Fields (trường rỗng do input nghèo ngữ cảnh)

- **Input** (log `10:38:12`): `"tôi là Thành, 29 tuổi tôi có 1 con … yêu cầu …"`
  → `"address": ""`, `"hobbies": ""`. Người dùng không nêu địa chỉ/sở thích nên
  trường rỗng — **không phải bug**, nhưng làm điểm `address` = 0 và giảm chất
  lượng semantic. Hệ thống vẫn chạy ổn (degrade gracefully, không crash) nhờ
  `_factor_scores` gán mặc định an toàn (`age=0.5`, `addr=0.0`).
- **Bài học**: cần **vòng hỏi lại** (clarify) khi thiếu trường quan trọng — hiện
  agent trả lời thẳng thay vì hỏi thêm.

---

## 5. Ablation Studies & Experiments

### Experiment 1: Extractor Prompt v1 vs v2 (gender disambiguation)

- **Diff**: thêm luật *"`gender` = giới tính NGƯỜI MÔ TẢ; 'tìm bạn nữ/nam' là yêu
  cầu, không suy giới tính từ đó"* + 1 few-shot.
- **Bằng chứng từ log** (cùng người dùng Hoàng, 2 lần liên tiếp):
  | Phiên bản input | Kết quả `gender` | Đúng? |
  | :--- | :--- | :--- |
  | v1 — không nói rõ giới tính | `Nữ` | ✗ (Top-5 sai toàn bộ) |
  | v2 — bổ sung "giới tính nam" | `Nam` | ✓ |
- **Result**: vá nhầm-giới-tính trên lớp input mơ hồ → kỳ vọng đưa lỗi giới tính
  về 0 mà không tăng token đáng kể.

### Experiment 2 (Bonus): Chatbot Baseline vs Agent

| Case | Chatbot (dán 30 hồ sơ, hỏi tự nhiên) | Agent | Winner |
| :--- | :--- | :--- | :--- |
| Hỏi đơn giản "ai hợp với tôi?" | Trả lời được nhưng **bịa điểm**, **lộ SĐT** | Top-5 có điểm kiểm chứng, ẩn SĐT | **Agent** |
| Lọc cứng khác giới | Hay lọt người cùng giới | 100% đúng giới (log) | **Agent** |
| "Chưa ưng ai, chờ người sau" | Không có cơ chế | Vào hàng đợi, tự ghép `Trang→Tuấn` | **Agent** |
| Bảo mật PII | Lộ SĐT trong câu trả lời | SĐT chỉ lộ sau `accept` | **Agent** |
| Câu chào hỏi xã giao | Tự nhiên, linh hoạt | Cứng nhắc theo pipeline | **Chatbot** |

→ Agent thắng ở **độ tin cậy, bảo mật, và tác vụ nhiều bước**; chatbot chỉ hơn ở
hội thoại tự do — đúng kỳ vọng lý thuyết.

---

## 6. Production Readiness Review

- **Security / PII**: SĐT **không** xuất hiện ở bước gợi ý — `compatibility.top_k`
  loại trường `phone` khỏi payload, chỉ `accept` mới lộ (consent-gated). ✓ Cần bổ
  sung: rate-limit, sanitize input để chống prompt-injection vào `extract`.
- **Guardrails**: pipeline tất định → **không có loop vô hạn**, chi phí mỗi task có
  trần (2 chat call + 1 embed). Cần thêm: schema-validate output `extract`
  (`_factor_scores` đã có default an toàn), retry + fallback model khi LLM lỗi.
- **Reliability gap đã ghi nhận**: (1) chưa có **backup provider**; (2) tính tuổi
  giao nhầm cho LLM (RCA §4-2); (3) chưa có **clarify loop** khi thiếu trường.
- **Scaling**: dataset hiện là **JSON file (30 hồ sơ)** → thay bằng **Postgres +
  pgvector / vector DB** để embedding và lọc Top-K ở quy mô vạn hồ sơ; hàng đợi
  JSON → message queue; cache embedding hồ sơ (hiện re-embed mỗi request — tối ưu
  lớn nhất về latency/cost).

---

## Phụ lục A — Dataset

`cupid/data/people.json`: **30 hồ sơ**, đa dạng 6 thành phố (Hà Nội, TP HCM, Đà
Nẵng, Hải Phòng, Huế, Cần Thơ), tuổi 22–36, đủ nam/nữ. Trường: `id`, `name`,
`age`, `gender`, `address`, `hobbies`, `requirements`, `phone` (chỉ lộ khi
`accept`).

## Phụ lục B — Cách tính độ tương thích

- **Lọc cứng**: chỉ ghép **khác giới** (thiếu thông tin giới → cho qua).
- **Điểm mềm (tổng = 1.0)**: `semantic` 0.50 (embedding cosine sở thích+mong muốn),
  `req_match` 0.20 (yêu cầu user khớp hồ sơ đối phương), `age` 0.12 (độ gần tuổi,
  `MAX_AGE_GAP=15`), `address` 0.18 (cùng tỉnh/thành). Ngưỡng ghép hàng đợi
  `MATCH_THRESHOLD = 0.60`.

## Phụ lục C — Cách chạy

```powershell
$env:PYTHONIOENCODING="utf-8"
# Web (FastAPI + giao diện 1 trang):
.\.venv\Scripts\python.exe -m cupid.app      # http://127.0.0.1:8000
# Terminal:
.\.venv\Scripts\python.exe -m cupid.main "Mình là Lan, nữ, 25t, Hà Nội, thích đọc sách và leo núi..."
```

---

> [!NOTE]
> File này là bản nộp chính thức theo `TEMPLATE_GROUP_REPORT.md`, đã đặt tên
> `GROUP_REPORT_LeThanhDat.md` trong `report/group_report/`.
