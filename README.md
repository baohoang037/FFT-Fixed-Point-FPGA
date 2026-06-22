# Fixed-Point Radix-2 FFT — Bit-Width Trade-off Study (NCKH)

Đề tài: **Evaluating Bit-Width Trade-offs for Fixed-Point Radix-2 FFT on FPGA**
N = 1024, Radix-2 DIT, định dạng Q1.(W−1), scaled FFT (÷2 mỗi tầng).

Chạy lại toàn bộ: `bash run_all.sh` (cần `python3 + numpy + matplotlib` và `iverilog`).

---

## Luồng nghiên cứu (5 bước)

### Bước 1 — Golden model (mô hình vàng) bit-accurate
`golden_model/golden_model.py`
- FFT Radix-2 DIT **số nguyên, bit-accurate**: lượng tử twiddle, làm tròn sau mỗi
  phép nhân phức, scaling ÷2 chống tràn sau mỗi tầng → output = DFT{x}/N.
- Đây là điểm sửa quan trọng nhất so với bản cũ: bản cũ chỉ lượng tử **đầu vào**
  rồi chạy `np.fft.fft` (dấu phẩy động), nên chỉ đo nhiễu lượng tử đầu vào và mọi
  đường SQNR bám đúng 6.02W+1.76 — tức đo nhầm. Bản này mô phỏng nhiễu tích lũy
  thật bên trong FFT.

### Bước 2 — Sinh dữ liệu kiểm thử
Chạy cùng `golden_model.py`, xuất ra:
- `test_vectors/tv_<sig>_bw<W>_{real,imag}_hex.txt` — đầu vào cho `$readmemh`.
- `test_vectors/tv_<sig>_bw<W>_float.txt` — bản float để đối chiếu.
- `test_vectors/twiddle_bw<W>_{cos,sin}_hex.txt` — **ROM hệ số xoay** (deliverable TV2).
- `expected_output/exp_<sig>_bw<W>_{real,imag}_hex.txt` — **đầu ra vàng** để testbench so.
- Một bộ lượng tử (round-half-up) dùng **chung** cho cả hex lẫn SQNR → không lệch.

6 tín hiệu: single_tone, multi_tone, impulse, all_zeros, max_value, random_noise.

### Bước 3 — Thiết kế RTL tham số hóa (Verilog)
`rtl/`
- `complex_mult.v` — bộ nhân phức Q1.(W−1) × Q1.(TW−1), làm tròn, nới 1 bit nguyên.
- `butterfly.v`    — butterfly Radix-2 DIT + scaling ÷2 + bão hòa.
- `twiddle_rom.v`  — ROM cos/sin nạp bằng `$readmemh`.
- `fft_top.v`      — **FFT 1024 điểm in-place, dùng chung 1 butterfly, FSM điều khiển**
                     (kiến trúc memory-based, tiết kiệm tài nguyên).
- Tất cả mở rộng qua **một** tham số `BIT_WIDTH` (parameter `DW`/`TW`).

### Bước 4 — Kiểm chứng đồng mô phỏng (đã PASS)
`tb/`
- `tb_butterfly.v` → so RTL butterfly với 200 vector golden ⇒ **bit-exact 200/200**.
- `tb_fft_top.v`   → so toàn bộ 1024 bin đầu ra với golden cho 5 tín hiệu, ở 12-bit
  và 16-bit ⇒ **bit-exact 1024/1024**.
- Kết luận: RTL khớp tuyệt đối golden model → mọi số liệu SQNR/độ chính xác đáng tin.

### Bước 5 — Phân tích & viết báo (bước cuối)
- `results/sqnr_results.csv`, `plots/*.png` — số liệu và đồ thị.
- Phần resource hiện là **mô hình giải tích** (LUT~W, DSP~W², BRAM~W), cần thay bằng
  số Vivado thật (xem dưới).

---

## Kết quả SQNR (dB) — N=1024, scaled FFT

| Tín hiệu        | W=8  | W=10 | W=12 | W=14 | W=16 |
|-----------------|------|------|------|------|------|
| single_tone     | 10.2 | 22.1 | 34.4 | 46.3 | 58.4 |
| multi_tone      |  7.2 | 19.8 | 31.2 | 43.5 | 55.4 |
| full-scale DC   | 15.3 | 27.3 | 39.4 | 51.4 | 63.4 |
| random_noise    |  2.5 | 14.5 | 26.5 | 38.5 | 50.6 |
| *input-only*    | 49.9 | 62.0 | 74.0 | 86.0 | 98.1 |

≈ 6 dB/bit; thấp hơn cận input-only ~40 dB = phần nhiễu xử lý của FFT.
impulse cho SQNR âm/inf do output 0.5/N **underflow** ở W thấp → hạn chế của scaled
FFT, là động lực cho block-floating-point (bàn trong phần thảo luận của bài báo).

---

## Việc còn lại trước khi viết báo (cần công cụ Vivado — máy mình tự chạy)
1. Tổng hợp `fft_top.v` cho W = 8/10/12/14/16 trên FPGA mục tiêu (vd Artix-7).
2. Trích **Utilization** (LUT, FF, BRAM, DSP), **Power**, **Timing (Fmax)**.
3. Thay 4 cột mô hình giải tích trong `plots/resource_tradeoff.png` bằng số thật,
   rồi mình cập nhật bài báo.

> Mình không chạy được Vivado trong môi trường này, nên phần PPA là số ước lượng có
> nhãn rõ ràng; còn golden model + RTL + kiểm chứng SQNR là số liệu thật đã verify.
