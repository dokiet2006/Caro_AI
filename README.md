# Caro AI 9×9 bằng Python

Chương trình cho **Bài 1** trong đề bài tập lớn giữa kỳ môn Trí tuệ nhân tạo 2026–2027:
chơi Caro, MiniMax + Alpha-Beta, MCTS + UCT, Random và thực nghiệm tái lập.
Có thêm rollout `tactical` để tự thực nghiệm hướng mở rộng A.

## 1. Chạy nhanh trên Windows

1. Giải nén toàn bộ thư mục `Caro_AI_Python`.
2. Dùng **Python 3.10 trở lên**, có thành phần Tcl/Tk của bộ cài Python.
3. Nhấp đúp `run_windows.bat`, hoặc mở terminal tại thư mục chứa `main.py` và chạy:

```powershell
python main.py
```

Nếu máy dùng Python Launcher:

```powershell
py -3 main.py
```

**Không cần cài thư viện bằng pip.** Giao diện dùng Tkinter; thuật toán, CSV, JSON,
biểu đồ SVG và trang kết quả HTML đều chỉ dùng thư viện chuẩn Python.
Linux cần có Tkinter và môi trường đồ họa để mở cửa sổ; terminal không cần chúng.

Trong VS Code/PyCharm: mở cả thư mục dự án, chọn interpreter Python >=3.10,
chạy `main.py`. Đặt working directory là thư mục chứa `main.py`.

## 2. Chơi bằng giao diện

- Mặc định: **X = Người chơi**, **O = MiniMax + Alpha-Beta**. X đi trước.
- Click giữa một ô trống. Cột A–I, hàng 1–9; E5 là ô chính giữa.
- Chọn tác nhân cho X/O, sửa tham số rồi bấm **Ván mới** để áp dụng.
- Người–máy: một bên Người chơi, bên kia Alpha-Beta/MCTS/Random.
- Máy–máy: chọn AI cho cả hai bên.
- **Tạm dừng / Tiếp tục**: dừng áp dụng nước đi tiếp theo; tác vụ đang tính có thể
  hoàn thành nhưng kết quả được giữ lại đến khi tiếp tục.
- **AI đi 1 bước**: tạm dừng rồi cho AI hiện tại đi đúng một nước.
- **Lưu nhật ký**: xuất JSON gồm tham số, seed, từng nước và thống kê tìm kiếm.
- **Mở nhật ký**: phát lại để khôi phục bàn cờ và lịch sử; ván được mở ở trạng thái tạm dừng.
  Nếu tiếp tục ván đã tải, bộ sinh ngẫu nhiên bắt đầu lại từ seed của mỗi tác nhân,
  không tiếp tục chính xác trạng thái RNG cũ. Nhật ký đánh dấu
  `continuation_rng_restarted=true`. Kết quả lịch sử vẫn được phát lại chính xác.
- **Nạp thế cờ**: nhập các nước luân phiên X, O, ví dụ `E5 D5 E4 D4 F4 F5`.
  Nước trùng ô, ngoài bàn hoặc sau khi ván đã kết thúc đều bị từ chối.
- Ô nước đi cuối có nền sáng và chấm xanh; chuỗi thắng được tô xanh.
- Bảng dưới cùng hiển thị nước chọn, độ sâu, thời gian, số nút, iteration và số lần cắt tỉa.

Luật: **ít nhất 5 quân liên tiếp** theo ngang, dọc hoặc hai đường chéo;
chuỗi 6+ vẫn thắng, chặn hai đầu vẫn thắng; không có luật cấm. Đầy bàn không ai thắng thì hòa.

### Các tham số

| Tham số | Ý nghĩa | Mặc định |
|---|---|---|
| `depth` / d | Số nửa lượt tìm kiếm MiniMax, tính cả nước hiện tại | 2 |
| `candidates` / K | Giới hạn mềm ứng viên MiniMax tại mỗi nút | 10 |
| `iterations` | Số vòng Selection–Expansion–Simulation–Backpropagation | 300 |
| `c` | Mức khám phá của UCT, phải hữu hạn và >0 | 1.4 |
| `rollout` | `random` cơ sở hoặc `tactical` ưu tiên thắng/chặn ngay | random |
| `seed` | Tái lập lựa chọn ngẫu nhiên khi chạy mới cùng tham số | 2026 |

Độ sâu cho phép 1–8; đề yêu cầu hỗ trợ ít nhất d=2. Nên demo d=2 hoặc 3, K=8–12.
Chi phí MiniMax tăng nhanh khi tăng cả d và K. Tạo ván mới/đóng cửa sổ có thể hủy tìm kiếm.
Chương trình không đặt giới hạn suy luận theo giây: dùng ngân sách depth/iteration.

## 3. Chạy trong terminal

Người đấu MCTS:

```powershell
python main.py play --x human --o mcts --o-iterations 500 --o-c 1.4
```

MCTS đấu Alpha-Beta:

```powershell
python main.py play --x mcts --o alphabeta --x-iterations 300 --o-depth 2 --o-candidates 10 --seed 2026
```

Đổi bên để MCTS đi sau:

```powershell
python main.py play --x alphabeta --o mcts --x-depth 2 --o-iterations 300
```

Kiểm tra một thế cờ có nước thắng ngay F5:

```powershell
python main.py play --x alphabeta --o random --moves B5 A5 C5 I1 D5 H1 E5 G2
```

Nhập ô như `E5`; `q` để dừng. Nhật ký mặc định `results/last_game.json`.
Dùng `--log duong_dan.json` để chọn tệp, `--quiet` để ẩn quá trình máy–máy.
Ván đang chơi cũng được lưu khi thoát bằng q, Ctrl+C hoặc hết đầu vào.

Xem toàn bộ lựa chọn:

```powershell
python main.py --help
python main.py play --help
python main.py experiment --help
```

## 4. Thực nghiệm theo đề

**Dữ liệu chạy sẵn:** mở `results/full_seed2026/index.html` trong trình duyệt.
Gói chứa 200 ván thật: 10 cấu hình × 20 ván, mỗi cấu hình gồm 10 cặp hoán đổi X/O.
Không cần chạy lại để xem bảng, đồ thị và nhật ký.

Chạy bộ thực nghiệm mới (thời gian phụ thuộc máy):

```powershell
python main.py experiment --games 20 --seed 2026 --output results/my_run
```

Bộ thực nghiệm gồm:

1. Alpha-Beta vs Random; MCTS vs Random; MCTS vs Alpha-Beta.
2. Khảo sát **c = 0.5, 1.0, 1.4, 2.0**, giữ iteration=300 và đối thủ Random cố định.
3. Khảo sát **iteration = 100, 300, 500**, giữ c=1.4 và đối thủ Random cố định.
4. So MiniMax thường và Alpha-Beta trên 4 thế cờ, cùng d=3, K=10.

Có thể đổi đối thủ khảo sát sang Alpha-Beta:

```powershell
python main.py experiment --games 40 --opponent alphabeta --depth 2 --candidates 10 --output results/vs_ab_40
```

Để thử nhanh đường ống xuất kết quả (số iteration khảo sát vẫn là 100/300/500):

```powershell
python main.py experiment --games 2 --smoke --iterations 100 --output results/smoke_check
```

`--smoke` luôn được đánh dấu trong dữ liệu và trang kết quả; số ván <20 không đạt yêu cầu đề.
Không ghi đè thư mục đã có `metadata.json`; chọn tên `--output` mới để giữ kết quả cũ.

| Tệp kết quả | Nội dung |
|---|---|
| `metadata.json` | Cấu hình CPU, hệ điều hành, Python, seed, ngân sách, tham số, trạng thái hoàn tất |
| `summary.csv` | Thắng–hòa–thua, tỷ lệ từng loại, thời gian trung bình mỗi cấu hình |
| `games.csv` | Kết quả, bên đi trước, seed, thời gian của từng ván |
| `games.jsonl` | Từng ván và toàn bộ nước đi/thống kê; mỗi dòng là một JSON |
| `pruning.csv` | MiniMax vs Alpha-Beta: nước đi, giá trị, nút, thời gian, tỷ lệ giảm nút |
| `01_c_rates.svg` | Tỷ lệ thắng/hòa/thua theo c |
| `02_iteration_rates.svg` | Tỷ lệ thắng/hòa/thua theo iteration |
| `03_iteration_time.svg` | Thời gian trung bình/nước theo iteration |
| `index.html` | Trang xem bảng và cả 3 đồ thị, hoạt động ngoại tuyến |

CSV dùng UTF-8 BOM để dễ mở bằng Excel. SVG có thể mở bằng trình duyệt hoặc chèn vào báo cáo.
Hạt giống theo cặp p (tính từ 0): subject=`seed+10000*p+11`, opponent=`seed+10000*p+29`;
dùng lại hai seed theo vai trò khi đổi bên. Cùng seed được dùng giữa cấu hình để giảm nhiễu.

Thời gian `mean_move_ms` là tổng thời gian chọn nước của tác nhân khảo sát chia số nước
của tác nhân đó, không gồm vẽ hình/ghi tệp. `mean_game_move_ms` là trung bình các
trung bình theo ván, được ghi riêng. Các ván được chạy tuần tự; thời gian vẫn chịu ảnh hưởng
của tải hệ thống. Cùng seed tái lập lựa chọn/kết quả; thời gian không thể giống tuyệt đối.

**Đọc kết quả thận trọng:** 20 ván là tối thiểu, không chứng minh một thuật toán luôn thắng.
Đối thủ Random có thể làm tỷ lệ thắng bão hòa, khó phân biệt các giá trị c; nên bổ sung
40–100 ván và đối thủ mạnh hơn khi viết phân tích. Kết quả đo trên máy kèm gói không
phải số đo trên máy cá nhân của bạn. Xem thêm `KET_QUA.md`.

## 5. Giải thích thuật toán và tổ chức mã nguồn

Đọc `THUAT_TOAN.md` để xem MAX/MIN, hàm đánh giá, cắt tỉa, góc nhìn phần thưởng MCTS
và giới hạn của từng phương pháp.

```text
Caro_AI_Python/
    main.py                  Điểm chạy
    run_windows.bat          Mở cửa sổ trên Windows
    README.md                Cài đặt, thao tác, thực nghiệm
    THUAT_TOAN.md             Giải thích thuật toán và cách bảo vệ mã
    KET_QUA.md               Tóm tắt số đo đi kèm
    requirements.txt         Chỉ cần thư viện chuẩn
    caro_ai/
        board.py             Luật, bitboard, đánh giá, ứng viên
        agents.py            Random, MiniMax/Alpha-Beta, MCTS/UCT
        gui.py               Tkinter; xử lý AI bằng worker thread
        cli.py               Giao diện dòng lệnh
        records.py           Ghi JSON và phát lại có kiểm tra luật
        experiments.py       Ghép cặp, thống kê, SVG, HTML
    tests/test_caro.py        Kiểm thử tính đúng đắn
    results/full_seed2026/    Dữ liệu 200 ván và đồ thị chạy thật
```

## 6. Kiểm thử

```powershell
python -m unittest discover -s tests -v
python main.py benchmark --depth 3 --candidates 10
```

20 kiểm thử bao gồm so bitboard với bộ kiểm tra hướng độc lập trên 100 ván ngẫu nhiên;
thắng 4 hướng, O thắng, chuỗi 6 bị chặn hai đầu, hòa 81 ô, chống tràn hàng;
nước đi lỗi; MiniMax và Alpha-Beta cùng nước/giá trị; giữ nước thắng/chặn;
UCT khi N=0; phần thưởng luân phiên; seed; số iteration; chọn theo N; hủy tác vụ;
ghi/đọc nhật ký và từ chối lịch sử không hợp lệ.

## 7. Hướng mở rộng A

Giao diện và CLI hỗ trợ `rollout=tactical`: nếu có nước thắng ngay thì đánh;
nếu không thì chặn một nước thắng ngay của đối thủ; còn lại chọn ngẫu nhiên toàn bàn.
Đây vẫn là heuristic, có thể thua trước hai mối đe dọa đồng thời.

```powershell
python main.py experiment --games 20 --include-heuristic --output results/with_heuristic
```

Lệnh thêm 2 cấu hình random/tactical với cùng đối thủ và ngân sách. Bộ dữ liệu 200 ván
đính kèm chỉ đánh giá Bài 1, **chưa có thực nghiệm cải thiện của rollout tactical**.

## 8. Phạm vi và nguồn

- Yêu cầu nguồn: tệp “Đề bài tập lớn giữa kỳ AI 26-27.pdf” được cung cấp cùng yêu cầu.
- Mã, hướng dẫn và bộ thực nghiệm được tạo với hỗ trợ ChatGPT (OpenAI).
  Nhóm bổ sung thành viên, phân công, giải thích và kết quả chạy trên máy của nhóm.
- Gói này là **chương trình và dữ liệu thực nghiệm**. Báo cáo PDF, slide và tên gói nộp
  theo mã lớp/số nhóm trong đề cần được chuẩn bị riêng; không có thông tin nhóm được tự điền.
- Không dùng thư viện AI/cờ có sẵn. Không có kết nối mạng hoặc thu thập dữ liệu khi chạy.
