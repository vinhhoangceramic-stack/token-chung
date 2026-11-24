"""Nơi DUY NHẤT khai báo đường dẫn log, tên các beta header và schema log."""
from __future__ import annotations

import os
import socket
from pathlib import Path

# Log ghi cục bộ từng máy, ngoài mọi repo: <thư mục người dùng>/token-chung-log/usage.jsonl
# (trên Windows là %USERPROFILE%\token-chung-log\usage.jsonl). Biến TOKEN_CHUNG_LOG chỉ dùng cho test.
DUONG_DAN_LOG = Path.home() / "token-chung-log" / "usage.jsonl"


def duong_dan_log() -> Path:
    return Path(os.environ["TOKEN_CHUNG_LOG"]) if os.environ.get("TOKEN_CHUNG_LOG") else DUONG_DAN_LOG


def ten_may() -> str:
    """Tên máy ghi vào log: biến TOKEN_CHUNG_MAY nếu có giá trị, không thì tên máy của hệ điều hành."""
    return (os.environ.get("TOKEN_CHUNG_MAY") or "").strip() or socket.gethostname()


# Schema log: đúng 13 trường, theo thứ tự này. `uoc_tinh` (từ v0.1.2) là true khi chi_phi_usd tính theo
# giá dự phòng vì model chưa có trong bảng giá; dòng cũ không có trường này thì coi là false.
TRUONG_LOG = (
    "du_an", "model", "effort", "input_tokens", "cache_creation_input_tokens",
    "cache_read_input_tokens", "output_tokens", "chi_phi_usd", "thoi_diem",
    "cache_miss_reason", "may", "lan", "uoc_tinh",
)

BETA_CHAN_DOAN_CACHE = "cache-diagnosis-2026-04-07"
BETA_EFFORT_THEO_MESSAGE = "mid-conversation-output-config-2026-07-01"
BETA_NGAN_SACH_VIEC = "task-budgets-2026-03-13"
BETA_COMPACTION = "compact-2026-09-04"
BETA_SUA_NGU_CANH = "context-management-2025-06-27"

SO_DIEM_CACHE_TOI_DA = 4
TOKEN_TINH_TOI_THIEU = 512          # phần tĩnh ngắn hơn mức này thì API bỏ qua cache (không lỗi)
NGAN_SACH_VIEC_TOI_THIEU = 20_000
