# Thiết kế và giải thích thuật toán

## Trạng thái và luật

`Board` là dataclass bất biến: hai bitboard X/O, người sắp đi `turn`, số quân `ply`,
người thắng `winner`, và `last_move`. Mỗi nước tạo trạng thái mới, tránh sửa nhầm bàn cờ
giữa các nhánh MiniMax hoặc luồng giao diện.

Mỗi hàng chiếm 10 bit nhưng chỉ dùng 9 bit. Bit đệm luôn bằng 0 để phép dịch không nối
đuôi hàng trước với đầu hàng sau. Bốn khoảng dịch 1, 10, 11, 9 tương ứng ngang, dọc và hai chéo.

Với khoảng dịch s, đặt `pair = b & (b >> s)`;
`pair & (pair >> (2*s)) & (b >> (4*s))` khác 0 khi có ít nhất 5 quân liền nhau.
Không kiểm tra hai đầu, nên không áp dụng luật chặn hai đầu. Chuỗi dài hơn 5 chứa một đoạn 5.

`Board.play()` là cổng kiểm tra chung cho giao diện, AI, terminal và nạp lịch sử:
phải còn đang chơi, ô trong 0..80 và ô trống. X đi trước; người chơi đổi dấu sau mỗi nước.

## MiniMax và Alpha-Beta

Mỗi lần suy luận lấy `root_player = board.turn` làm góc nhìn cố định:

- MAX là lượt của `root_player`, lấy giá trị lớn nhất.
- MIN là lượt đối thủ, lấy giá trị nhỏ nhất.
- Dừng ở thắng/hòa hoặc hết số nửa lượt d.
- Thắng: `100_000_000 - ply`; thua là giá trị đối dấu; hòa bằng 0.
  Như vậy tác nhân ưu tiên thắng sớm, trì hoãn thua trong độ sâu xét được.

Hàm đánh giá không kết thúc: xét tất cả cửa sổ 5 ô theo 4 hướng.
Nếu cửa sổ có cả X và O thì không bên nào đóng góp. Cửa sổ chưa bị chặn có n quân
dùng trọng số `w[n] = [0, 2, 12, 120, 2500, 1_000_000]`.

`score_X = tổng w[số X] của cửa sổ không có O − tổng w[số O] của cửa sổ không có X`.
Kết quả từ góc nhìn root là `root_player * score_X`.
Đây là heuristic theo cửa sổ, không phải bộ nhận diện đầy đủ mọi dạng “ba thoáng / bốn thoáng”.
Điểm thắng/thua luôn vượt mức tổng heuristic ở một trạng thái chưa kết thúc.

Alpha là giá trị tốt nhất MAX đã bảo đảm; beta là giá trị tốt nhất MIN đã bảo đảm.
Khi `alpha >= beta`, nhánh còn lại không thể thay đổi quyết định của tổ tiên liên quan,
nên cắt bỏ. `cutoffs` đếm số lần dừng vòng lặp, không đếm số nút giả định bị bỏ qua.

### Giới hạn ứng viên

1. Bàn trống: chọn ô trung tâm E5.
2. Các bàn khác: xét ô trống trong khoảng cách Chebyshev <=2 từ ít nhất một quân.
3. Giữ toàn bộ nước thắng ngay của mình và toàn bộ nước có thể chặn thắng ngay của đối thủ.
4. Điền các chỗ còn lại đến K bằng điểm tạo/chặn chuỗi; ưu tiên gần trung tâm khi bằng điểm.

K là **giới hạn mềm**: nếu có nhiều nước chiến thuật, có thể vượt K để không loại chúng.
Mọi nước thắng/chặn tức thời đều gần một quân sẵn có nên không bị mất ở bước 2.
Giới hạn ứng viên là heuristic tìm kiếm, không thay đổi tập nước hợp lệ của trò chơi.
Do đó không bảo đảm quyết định tối ưu trên toàn bộ cây 81 ô.

MiniMax thường dùng cùng cây ứng viên, thứ tự, hàm đánh giá và độ sâu với Alpha-Beta.
Hai bản chỉ khác việc có thực hiện điều kiện cắt tỉa hay không.
`benchmark` xác nhận cùng giá trị và cùng nước chọn trước khi xuất so sánh số nút.
Số nút tính cả gốc và mọi lần gọi đệ quy, kể cả lá.

## MCTS + UCT

Không giới hạn K cho MCTS: expansion có thể chọn **mọi nước đi hợp lệ**.
Một iteration:

1. **Selection:** nếu nút chưa kết thúc và đã mở hết nước đi, chọn nút con có UCT lớn nhất.
2. **Expansion:** lấy ngẫu nhiên một nước chưa thử, tạo đúng một nút con.
3. **Simulation:** chơi từ nút đó đến thắng/hòa thật, không cắt rollout sớm bằng điểm heuristic.
4. **Backpropagation:** tăng visits và cộng reward từ nút đó ngược đến gốc.

UCT(i) = Wᵢ / Nᵢ + c × sqrt(ln(Nₚ) / Nᵢ).

- Nᵢ: lượt thăm con; Nₚ: lượt thăm cha.
- Wᵢ: tổng phần thưởng từ góc nhìn **người vừa đánh để tạo nút con i**.
- c>0: c lớn tăng sức nặng khám phá, không đồng nghĩa chơi mạnh hơn.
- Nᵢ=0 được trả +vô cực, không chia 0. Expansion còn ưu tiên thử nước chưa mở.

### Quy ước góc nhìn phần thưởng

Mỗi nút lưu `player_just_moved = -node.board.turn`.
Nếu kết quả mô phỏng thắng cho người đó thì cộng 1; hòa cộng 0.5; thua cộng 0.
Cùng một kết quả được chuyển thành phần thưởng riêng tại từng nút trên đường lên.
Không cộng nguyên một phần thưởng của người ở gốc cho mọi tầng.

Ví dụ X thắng trong rollout:

| Nút | Người vừa đi | Reward |
|---|---|---|
| Sau nước X | X | 1 |
| Sau nước O | O | 0 |
| Sau nước X tiếp theo | X | 1 |

Khi cha chọn con, “người vừa đi của con” chính là “người sắp đi ở cha”.
Vì vậy chọn max UCT ở mọi tầng vẫn mô hình hóa đối thủ đang tối ưu lợi ích của họ.
Reward của gốc dùng cùng quy ước nhưng không tham gia lựa chọn của một nút cha nào;
root.visits mới là số cần cho UCT ở tầng đầu.

### Chọn nước cuối

Sau đúng số iteration cấu hình, chọn con có **N lớn nhất**; W/N chỉ phá hòa khi cùng N.
Một nhánh có W/N rất cao nhưng mới thử vài lần dễ bị nhiễu. Nhánh được thăm nhiều đã
nhận nhiều ngân sách sau quá trình cân bằng khám phá–khai thác, nên thường ổn định hơn.
Đây là quy tắc robust child, không phải bảo đảm thắng.

`nodes` của MCTS là số nút cây đã tạo, có cả gốc, không phải số nước mô phỏng.
`rollout_moves` đếm riêng số bước mô phỏng; `max_tree_depth` là độ sâu cây đã đạt.
`root_children` trong nhật ký chơi riêng lưu N, W và W/N để kiểm tra quy tắc chọn nước.
Nhật ký thực nghiệm bỏ bảng con để gọn hơn, vẫn giữ các thống kê chính.

### Hạn chế và hướng mở rộng

- Ngân sách 100–500 iteration chia cho nhiều nước hợp lệ có thể quá nhỏ để thấy chiến thuật sâu.
- Rollout ngẫu nhiên toàn bàn có nhiều nước xa, dễ đánh giá thấp một mối đe dọa bắt buộc chặn.
- Tăng iteration thường tăng thời gian nhưng không bảo đảm tỷ lệ thắng tăng trong một mẫu nhỏ.
- MiniMax phụ thuộc hàm đánh giá/độ sâu/K; MCTS phụ thuộc c, ngân sách và chất lượng rollout.
- `tactical` là tùy chọn rollout ưu tiên thắng/chặn tức thời; cần đo thêm trước khi kết luận cải thiện.
- Chưa dùng transposition table, tree reuse, opening book hoặc mạng nơron để giữ mã dễ giải thích.

## Gợi ý demo và vấn đáp

1. Người–máy với Alpha-Beta d=2, K=10; chỉ bảng thống kê.
2. Máy–máy MCTS c=1.4, 300 iteration vs Alpha-Beta.
3. Nạp `B5 A5 C5 I1 D5 H1 E5 G2`: X có nước F5 thắng ngay.
4. Chạy `python main.py benchmark --depth 3 --candidates 10`: so nút và nước đi.
5. Mở `results/full_seed2026/index.html`, giải thích việc đổi bên và seed.
6. Chỉ vị trí bốn giai đoạn trong `MCTSAgent.choose()` và reward trong `backpropagate()`.
7. Phân biệt budget `iterations`, số nút cây và số bước rollout.
8. Giải thích vì sao kết quả 20/20 trước Random không chứng minh bất bại.
