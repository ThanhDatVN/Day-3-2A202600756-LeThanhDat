# 💘 Cupid AI — Agent mai mối từ mô tả ngôn ngữ tự nhiên

> Người dùng chỉ cần **tả vài dòng về bản thân**, AI tự hiểu, tìm người hợp nhất,
> đưa lời khuyên kết nối, và cho phép **đồng ý để nhận số điện thoại** hoặc **vào
> hàng đợi** chờ người phù hợp tiếp theo.

---

## 1. 🎯 Vấn đề (Pain point)

- Người đăng ký hẹn hò mô tả bản thân bằng **văn nói tự do**, mỗi người một kiểu.
- Admin phải đọc và **ghép tay** → tốn thời gian, dễ sót.
- So khớp "word-by-word" kém chính xác: "leo núi" và "trekking" là cùng sở thích
  nhưng khác chữ.
- Chưa có cơ chế cho người dùng **chủ động đồng ý** hay **chờ đợt sau** khi chưa ưng.

## 2. 💡 Ý tưởng

Một **AI Agent** đứng giữa người dùng và kho hồ sơ:
1. Hiểu mô tả tự nhiên của người dùng (NLP trích xuất).
2. Tính độ tương thích với 30 hồ sơ có sẵn.
3. Gợi ý **Top-5** kèm **đánh giá + lời khuyên** của AI.
4. Người dùng **Đồng ý** (nhận SĐT) hoặc **Không ưng → vào hàng đợi**.

---

## 3. 🔄 Workflow của Agent (sơ đồ thuyết trình)

```
  👤 NGƯỜI DÙNG nhập mô tả tự nhiên
  "Mình là Hùng, 29t, nam, Hà Nội, mê trekking & chụp ảnh,
   muốn tìm cô gái yêu thiên nhiên, thích đi phượt"
                       │
   ┌───────────────────▼─────────────────────────────────────┐
   │ ①  TRÍCH XUẤT THÔNG TIN   (OpenAI – JSON mode)           │
   │     → { name, age, gender, address, hobbies, requirements }│
   └───────────────────┬─────────────────────────────────────┘
                       │
   ┌───────────────────▼─────────────────────────────────────┐
   │ ②  KIỂM TRA HÀNG ĐỢI                                     │
   │     Có ai đang "chờ" mà hợp với người mới này không?      │
   └───────────────────┬─────────────────────────────────────┘
                       │
   ┌───────────────────▼─────────────────────────────────────┐
   │ ③  TÍNH ĐỘ TƯƠNG THÍCH  (hàm code, deterministic)        │
   │     • Lọc CỨNG: chỉ giữ người KHÁC GIỚI                   │
   │     • Điểm ĐA TẦNG:                                       │
   │         ngữ nghĩa 0.50 (embedding) + yêu cầu 0.20         │
   │         + tuổi 0.12 + địa điểm 0.18                       │
   └───────────────────┬─────────────────────────────────────┘
                       │
   ┌───────────────────▼─────────────────────────────────────┐
   │ ④  LẤY TOP 5 điểm cao nhất                               │
   └───────────────────┬─────────────────────────────────────┘
                       │
   ┌───────────────────▼─────────────────────────────────────┐
   │ ⑤  ĐÁNH GIÁ + LỜI KHUYÊN  (OpenAI)                       │
   │     Mỗi người: nhãn hợp + nhận xét + cách bắt chuyện      │
   └───────────────────┬─────────────────────────────────────┘
                       │
   ┌───────────────────▼─────────────────────────────────────┐
   │ ⑥  TRẢ VỀ GIAO DIỆN  (KHÔNG lộ số điện thoại)            │
   └───────────────────┬─────────────────────────────────────┘
                       │
        ┌──────────────┴───────────────┐
        ▼                               ▼
  ⑦a 💚 ĐỒNG Ý người nào          ⑦b ❌ KHÔNG ƯNG AI
     → Hệ thống trả về SĐT            → Lưu hồ sơ vào HÀNG ĐỢI (database)
       để hai bên liên hệ            → Khi có người mới phù hợp xuất hiện,
                                        hệ thống TỰ BÁO GHÉP
```

**Một câu để chốt khi thuyết trình:**
> *Người dùng tả tự nhiên → AI trích xuất → tính điểm → Top-5 → AI đánh giá →
> người dùng Đồng ý (nhận SĐT) hoặc vào hàng đợi.*

---

## 4. 🧩 Vì sao tốt hơn cách cũ?

| | Cách cũ (thủ công / word-by-word) | Cupid AI |
| :--- | :--- | :--- |
| Nhập liệu | điền form cứng nhắc | tả tự nhiên bằng lời |
| Hiểu sở thích | so khớp từng chữ | **embedding** hiểu nghĩa ("trekking"≈"leo núi") |
| Gợi ý | admin chọn tay | **Top-5 tự động + lời khuyên AI** |
| Khi chưa ưng | bỏ lửng | **hàng đợi**, tự ghép khi có người mới |
| Riêng tư | lộ thông tin | **SĐT chỉ lộ khi đồng ý** |

---

## 5. 🗂️ Dữ liệu (30 hồ sơ, JSON)

`cupid/data/people.json` — mỗi hồ sơ: `id, name, age, gender, address, hobbies,
requirements, phone`. (SĐT được giấu, chỉ trả về khi người dùng đồng ý.)

---

## 6. ⚙️ Công nghệ

- **Python + FastAPI** (backend & API) · **HTML/JS** (giao diện 1 trang).
- **OpenAI**: `gpt-4o-mini` (trích xuất JSON + đánh giá) · `text-embedding-3-small`
  (tính tương thích ngữ nghĩa).
- **Database**: file JSON (`people.json`, `waitlist.json`) — dễ nâng lên
  Postgres/Google Sheet sau này.
- Mọi lời gọi AI được **ghi log** (token/độ trễ) trong `logs/`.

---

## 7. ▶️ Demo

```powershell
$env:PYTHONIOENCODING="utf-8"

# Giao diện web:
.\.venv\Scripts\python.exe -m cupid.app        # mở http://127.0.0.1:8000

# Hoặc terminal:
.\.venv\Scripts\python.exe -m cupid.main "Mình là Lan, nữ, 25t, Hà Nội, thích đọc sách và leo núi. Tìm người chân thành, thích du lịch."
```

**Kịch bản demo gợi ý:**
1. Nhập mô tả của một người → xem Top-5 + lời khuyên.
2. Bấm **Đồng ý** một người → màn hình hiện **số điện thoại**.
3. Nhập một người khác, **từ chối hết** → bấm **"chờ người tiếp theo"** (vào hàng đợi).
4. Nhập người mới hợp với người đang chờ → hệ thống **báo ghép** ngay.

---

## 8. 🚀 Hướng phát triển

- Chuẩn hóa địa chỉ không dấu/viết tắt ("Ha Noi" ≈ "Hà Nội").
- Gửi thông báo ghép qua **Email/Zalo** tự động.
- Kết nối **Google Sheet thật** thay file JSON.
- Gợi ý **địa điểm hẹn hò** theo sở thích chung.
