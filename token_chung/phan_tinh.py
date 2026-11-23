"""Dựng phần tĩnh của prompt (tools rồi system) và đặt cache_control ở cuối phần tĩnh.

Dùng chung cho lời gọi thường (khach.py) và batch (lo.py) để hai đường giống hệt nhau.
"""
from __future__ import annotations

import copy

from . import cau_hinh


def dau_cache(ttl: str) -> dict:
    if ttl not in ("5m", "1h"):
        raise ValueError("ttl phải là '5m' hoặc '1h'")
    return {"type": "ephemeral", "ttl": "1h"} if ttl == "1h" else {"type": "ephemeral"}


def chuan_hoa_system(system) -> list[dict]:
    if not system:
        return []
    if isinstance(system, str):
        return [{"type": "text", "text": system}]
    return copy.deepcopy(list(system))


def dem_diem_cache(*nhom) -> int:
    """Đếm số cache_control đã có trong các khối (tools / system / messages)."""
    n = 0
    for khoi in nhom:
        for k in khoi or []:
            if isinstance(k, dict):
                if "cache_control" in k:
                    n += 1
                nd = k.get("content")
                if isinstance(nd, list):
                    n += sum(1 for c in nd if isinstance(c, dict) and "cache_control" in c)
    return n


def dung(tools, system, ttl: str) -> tuple[list[dict], list[dict]]:
    """Trả (tools, system) đã đặt đúng MỘT điểm cache ở cuối phần tĩnh.

    Điểm trên khối system cuối cùng cache luôn cả tools (tools đứng trước system).
    Không có system thì đặt trên tool cuối cùng. Phần tĩnh dưới cau_hinh.TOKEN_TINH_TOI_THIEU token
    thì API tự bỏ qua, không lỗi, không tính phí ghi.
    """
    t = copy.deepcopy(list(tools or []))
    s = chuan_hoa_system(system)
    for k in t + s:                      # bỏ dấu cũ để chỉ còn một điểm do gói này đặt
        k.pop("cache_control", None)
    if s:
        s[-1]["cache_control"] = dau_cache(ttl)
    elif t:
        t[-1]["cache_control"] = dau_cache(ttl)
    return t, s


def kiem_so_diem(tools, system, messages, co_tu_dong: bool) -> None:
    n = dem_diem_cache(tools, system, messages) + (1 if co_tu_dong else 0)
    if n > cau_hinh.SO_DIEM_CACHE_TOI_DA:
        raise ValueError(f"Quá {cau_hinh.SO_DIEM_CACHE_TOI_DA} điểm cache_control ({n}). Bỏ bớt dấu trong messages.")
