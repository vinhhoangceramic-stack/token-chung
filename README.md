# token-chung

Lớp bọc dùng chung cho mọi lời gọi Anthropic (Python). Mọi lời gọi Messages API và Batch API của dự án đi qua gói này, không gọi SDK trực tiếp.

## Cài đặt

Ghim theo thẻ phiên bản, không cài từ nhánh chính:

```
pip install "git+https://github.com/<chu-so-huu>/token-chung@v0.1.1"
```

Trong `requirements.txt`:

```
token-chung @ git+https://github.com/<chu-so-huu>/token-chung@v0.1.1
```

Khóa API đọc từ biến `ANTHROPIC_API_KEY` trong `.env` của chính ứng dụng (xem `.env.example`). Không đặt khóa ở biến môi trường toàn cục của máy.

## Gói làm gì

1. **Ghi log**: mỗi lời gọi một dòng JSONL vào `%USERPROFILE%\token-chung-log\usage.jsonl` (Windows) hoặc `~/token-chung-log/usage.jsonl`. Log nằm ngoài mọi repo, mỗi máy một file, không tự gộp. Đường dẫn khai báo một chỗ: `token_chung/cau_hinh.py`.
2. **Tính tiền**: `chi_phi_usd` tính từ `token_chung/gia_model.json` (file giá duy nhất, có ghi ngày kiểm chứng). Giá vào/ra là USD cho 1 triệu token; mọi khóa `he_so_*` là hệ số nhân với giá vào của chính model đó.
3. **Giữ cache**: thứ tự prompt cố định `tools` → `system` → `messages`. Một điểm `cache_control` ở cuối phần tĩnh, cộng điểm tự động cho đuôi hội thoại; tối đa 4 điểm. Phần tĩnh dưới 512 token thì API tự bỏ qua cache.
4. **Chẩn đoán cache**: mỗi lượt gửi `diagnostics.previous_message_id` và ghi `cache_miss_reason` vào log.
5. **Không đổi giữa phiên**: `tools`, `system`, `thinking`, effort cấp request, model chốt khi tạo phiên. Đổi effort theo từng lượt thì dùng `tin_nhan_doi_effort()`, cách này không làm mất cache.

### Schema log (12 trường)

`du_an, model, effort, input_tokens, cache_creation_input_tokens, cache_read_input_tokens, output_tokens, chi_phi_usd, thoi_diem, cache_miss_reason, may, lan`

`lan` là `api` (gọi bằng khóa API) hoặc `max` (chạy bằng Claude Code; khi đó chỉ ghi `du_an, may, thoi_diem, lan`, `chi_phi_usd` để trống).

### TTL cache

Mặc định 5 phút. `ttl="tu_dong"`: dùng 1 giờ khi có ít nhất 1 trong 20 khoảng nghỉ gần nhất giữa hai lời gọi rơi vào 5–60 phút. Batch luôn dùng 1 giờ.

## Dùng

```python
from token_chung import Phien, tin_nhan_doi_effort

phien = Phien("ten-du-an", "claude-sonnet-5-5", system=HUONG_DAN, tools=CONG_CU,
              effort="medium", max_tokens=64000, ttl="tu_dong")
messages = [{"role": "user", "content": "..."}]
tl = phien.goi(messages)
messages.append({"role": "assistant", "content": tl.content})
```

Lời gọi một lượt, trả JSON theo schema (structured output), nội dung khác nhau mỗi lần:

```python
phien = Phien("ten-du-an", "claude-haiku-5-5", dinh_dang={"type": "json_schema", "schema": SCHEMA},
              effort="low", max_tokens=2000, cache_hoi_thoai=False)
```

`cache_hoi_thoai=False` tắt điểm cache tự động ở đuôi hội thoại: với lời gọi một lượt không có phần tĩnh dùng lại, điểm đó chỉ ghi cache (1,25 lần giá vào) mà không bao giờ được đọc lại.

Lỗi khi tính tiền hoặc ghi log (ví dụ model chưa có trong bảng giá) chỉ được ghi cảnh báo vào logger `token_chung`; lời gọi API vẫn trả kết quả bình thường, `chi_phi_usd` để trống.

Batch (giảm 50%, cộng dồn với cache):

```python
from token_chung import lo
batch_id = lo.gui_lo(client, "claude-haiku-5-5", [("viec-1", messages_1), ("viec-2", messages_2)],
                     system=HUONG_DAN, effort="low", max_tokens=4000)
for r in lo.doc_ket_qua(client, batch_id, "ten-du-an", effort="low"):
    ...
```

Claude Agent SDK: `nhat_ky.ghi_tu_agent_sdk("ten-du-an", result_message)`. Dự án chạy bằng Claude Code: `nhat_ky.ghi_lan_max("ten-du-an")`.

Tổng hợp log: `python -m token_chung.bao_cao`.

## Quy tắc

- Không gửi `thinking: {"type": "disabled"}` và không dùng `budget_tokens`; giảm suy nghĩ bằng `output_config.effort`.
- `max_tokens` là trần chống chạy quá, không phải công cụ tiết kiệm (việc agent đặt 64000). Tiết kiệm output bằng cách ghi rõ định dạng và độ dài mong muốn trong prompt.
- Không bật fast mode hay `inference_geo` khác mặc định nếu không có lý do ghi rõ.
- Chọn model và effort theo bảng đo (cấu hình rẻ nhất đạt ngưỡng chất lượng), không chốt cứng.

## Kiểm thử

```
python -m unittest discover -s tests -t .
```
