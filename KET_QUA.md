# Kết quả chạy kèm chương trình

Dữ liệu thực nghiệm đã chạy thật, không phải số liệu minh họa.

- Python: 3.12.14
- CPU: AMD EPYC 9V74 80-Core Processor
- Hệ điều hành: Linux-6.18.55-x86_64-with-glibc2.39
- Số CPU logic nhìn thấy: 9
- Seed gốc: 2026
- Tổng: 200 ván, 20 ván/cấu hình (10 cặp đổi bên)
- Thời gian toàn bộ bộ thực nghiệm: 71.96 giây trên môi trường này

Ngân sách: Alpha-Beta d=2, K=10; MCTS cơ sở rollout random toàn bàn.
Khảo sát c giữ iteration=300; khảo sát iteration giữ c=1.4. Đối thủ khảo sát là Random.
Thời gian dưới đây là trung bình theo số nước đi của tác nhân ở cột tác nhân.

| Nhóm | Cấu hình | Tác nhân | Đối thủ | Thắng–Hòa–Thua | Tỷ lệ thắng | ms/nước |
|---|---|---|---|---:|---:|---:|
| round_robin | alphabeta_vs_random | alphabeta | random | 20–0–0 | 100% | 2.378 |
| round_robin | mcts_vs_random | mcts | random | 20–0–0 | 100% | 33.744 |
| round_robin | mcts_vs_alphabeta | mcts | alphabeta | 0–0–20 | 0% | 34.256 |
| c_sweep | c=0.5 | mcts | random | 20–0–0 | 100% | 31.504 |
| c_sweep | c=1.0 | mcts | random | 20–0–0 | 100% | 28.516 |
| c_sweep | c=1.4 | mcts | random | 20–0–0 | 100% | 25.952 |
| c_sweep | c=2.0 | mcts | random | 19–0–1 | 95% | 25.335 |
| iteration_sweep | iterations=100 | mcts | random | 15–0–5 | 75% | 7.548 |
| iteration_sweep | iterations=300 | mcts | random | 20–0–0 | 100% | 24.937 |
| iteration_sweep | iterations=500 | mcts | random | 19–0–1 | 95% | 45.373 |

## MiniMax và Alpha-Beta trên cùng cây ứng viên

Cùng độ sâu d=3, K=10, hàm đánh giá và thứ tự nước đi. Cùng nước chọn và giá trị.

| Thế cờ | Nước | Nút MiniMax | Nút Alpha-Beta | Giảm nút |
|---|---|---:|---:|---:|
| empty | E5 | 112 | 31 | 72.3% |
| opening | D6 | 1111 | 139 | 87.5% |
| middle | E3 | 1111 | 175 | 84.2% |
| threat | F5 | 1001 | 110 | 89.0% |

## Nhận xét từ dữ liệu này

- MiniMax + Alpha-Beta d=2 mạnh hơn MCTS cơ sở trong đối sánh trực tiếp ở ngân sách 300 iteration của lần chạy này.
- Trước Random, kết quả có thể bão hòa ở mức cao; khác biệt c trong mẫu 20 ván chưa đủ để kết luận cấu hình nào tốt nhất.
- Cần đọc cả tỷ lệ thua và chi phí thời gian. Tăng iteration không bảo đảm tỷ lệ thắng tăng đơn điệu trong mẫu nhỏ.
- Giảm số nút Alpha-Beta chỉ nói về cây ứng viên đã chọn, không chứng minh đã tìm toàn bộ cây 81 ô.
- Thời gian đo trong môi trường dùng chung có thể dao động; hãy chạy lại trên máy nhóm khi lập báo cáo.

## Xác minh

- 20 kiểm thử tự động đã đạt.
- Phát lại toàn bộ 200 ván qua kiểm tra luật; đúng kết quả kết thúc, đủ 10 cặp/cấu hình.
- Tính lại thắng/hòa/thua và thời gian trung bình từ nhật ký, khớp bảng tổng hợp.
- Chạy lại một ván MCTS vs Random bằng cùng seed, khớp toàn bộ chuỗi nước đi.
- Kiểm tra cú pháp XML của cả 3 biểu đồ SVG.
- Giao diện Tkinter chưa được chạy trực tiếp trong môi trường tạo gói vì không có màn hình X; thuật toán và chế độ terminal đã được chạy.

Mở `results/full_seed2026/index.html` để xem đồ thị và tải CSV ngoại tuyến.
Chưa đánh giá thực nghiệm tùy chọn rollout tactical trong gói kết quả này.
