# Đề tài: Agent mai mối từ Google Sheet
# mấy nghìn người đăng kí, hàng chục tình nguyện viên nhưng vẫn phải mất 1- 2 tuần mới hòm hòm được, còn rất nhiều bạn case khó không được match
## 🎯 Pain Point
- Chương trình dating thu thập dữ liệu qua Google Form → Google Sheet.
- Admin phải match thủ công dựa trên nhiều trường thông tin (tên, tuổi, địa chỉ, sở thích…).
- Match thủ công tốn thời gian, dễ sai sót, không tận dụng hết dữ liệu.
- Người dùng điền mục tiêu, sở thích cùng 1 vấn đề nhưng rất nhiều cách nói khiến việc word by word tỉ lệ chính xác không cao
- Sau đó việc match các bnja cũng như nhắn tin, email cho từng bạn rất tốn thời gian và công sức
- Các app dating hiện tại chỉ dựa trên profile cơ bản, chưa có tool nào xử lý trực tiếp dữ liệu Google Sheet với nhiều trường phức tạp.

## 💡 Ý tưởng
- Xây dựng một **Agent mai mối** có khả năng:
  1. **Đọc dữ liệu từ Google Sheet** (profile người dùng).
  2. **Chuẩn hóa thông tin** (ví dụ: “Hà Nội” và “HN” coi là một).
  3. **Tính điểm tương đồng** giữa các profile bằng AI embedding, có thể dùng api của open ai (sở thích, thói quen, giá trị sống).
  4. **Tự động tạo cặp match** dựa trên điểm tương đồng cao nhất + filter (độ tuổi, địa điểm).
  5. **Xuất kết quả** ra Google Sheet mới hoặc gửi email tự động cho người dùng.

## ⚙️ Quy trình hoạt động
1. Người dùng đăng ký qua Google Form → dữ liệu đổ về Google Sheet.
2. Agent xử lý dữ liệu:
   - Chuẩn hóa text.
   - Tính similarity bằng AI.
   - Ghép đôi theo điểm tương đồng.
3. Agent xuất kết quả:
   - Danh sách match trong Google Sheet mới.
   - Email thông báo match cho người dùng.
   - (Nâng cấp) Gợi ý địa điểm hẹn hò phù hợp.
## công nghệ sử dụng
Google API: đọc/ghi dữ liệu từ Google Sheet.
Python + FastAPI: backend xử lý dữ liệu và chạy agent.
AI Embedding (Sentence-BERT, OpenAI Embeddings): tính similarity giữa profile.
Database: Postgres/MySQL để lưu dữ liệu sạch + kết quả match.
Frontend/Dashboard: React hoặc đơn giản là Google Data Studio để hiển thị kết quả.

## 📈 Tính thực chiến
- Admin: tiết kiệm thời gian, giảm sai sót.
- Người dùng: match chính xác hơn, trải nghiệm tốt hơn.
- Thị trường: chưa có agent chuyên biệt cho Google Sheet dating.
- Khác biệt: xử lý dữ liệu phức tạp nhiều trường, dùng AI để match sâu hơn word-by-word.

