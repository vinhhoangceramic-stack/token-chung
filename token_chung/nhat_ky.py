"""Ghi mỗi lời gọi một dòng JSONL, đúng 12 trường trong cau_hinh.TRUONG_LOG.

Đường dẫn log khai báo một chỗ: cau_hinh.DUONG_DAN_LOG (mặc định trong thư mục người dùng, ngoài mọi repo).
"""
from __future__ import annotations

import json
import socket
import threading
from datetime import datetime, timezone

from . import cau_hinh

_khoa = threading.Lock()


def ghi(**truong) -> dict:
    la = set(truong) - set(cau_hinh.TRUONG_LOG)
    if la:
        raise ValueError(f"Trường lạ không có trong schema log: {sorted(la)}")
    dong = {k: truong.get(k) for k in cau_hinh.TRUONG_LOG}
    if dong["lan"] not in ("max", "api"):
        raise ValueError("lan phải là 'max' hoặc 'api'")
    dong["thoi_diem"] = dong["thoi_diem"] or datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    dong["may"] = dong["may"] or socket.gethostname()
    p = cau_hinh.duong_dan_log()
    p.parent.mkdir(parents=True, exist_ok=True)
    with _khoa, open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(dong, ensure_ascii=False) + "\n")
    return dong


def ghi_lan_max(du_an: str) -> dict:
    """Dự án chạy bằng Claude Code (gói Max): chỉ ghi du_an, may, thoi_diem, lan; chi_phi_usd để trống."""
    return ghi(du_an=du_an, lan="max")


def ghi_tu_agent_sdk(du_an: str, ket_qua, model: str | None = None, effort: str | None = None) -> dict:
    """Ghi từ ResultMessage của Claude Agent SDK. Trường SDK không cung cấp thì để trống, không tự tính."""
    u = getattr(ket_qua, "usage", None) or {}
    lay = (lambda k: u.get(k)) if isinstance(u, dict) else (lambda k: getattr(u, k, None))
    return ghi(du_an=du_an, model=model, effort=effort, lan="api",
               input_tokens=lay("input_tokens"), cache_creation_input_tokens=lay("cache_creation_input_tokens"),
               cache_read_input_tokens=lay("cache_read_input_tokens"), output_tokens=lay("output_tokens"),
               chi_phi_usd=getattr(ket_qua, "total_cost_usd", None))
