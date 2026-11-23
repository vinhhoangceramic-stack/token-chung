"""Tính chi_phi_usd từ gia_model.json (file giá duy nhất).

Giá vào/ra trong file là USD cho 1 triệu token. Mọi khóa he_so_* là hệ số nhân với giá vào của chính model.
"""
from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources


@lru_cache(maxsize=1)
def bang_gia() -> dict:
    return json.loads(resources.files("token_chung").joinpath("gia_model.json").read_text(encoding="utf-8"))


def tinh_chi_phi(model: str, input_tokens: int = 0, ghi_cache_5m: int = 0, ghi_cache_1h: int = 0,
                 doc_cache: int = 0, output_tokens: int = 0, batch: bool = False) -> float | None:
    """Trả USD, hoặc None nếu model không có trong bảng giá (không đoán)."""
    bg = bang_gia()
    g = bg["model"].get(model)
    if g is None:
        return None
    hs = bg["he_so_chung"]
    vao, ra = g["vao_usd"], g["ra_usd"]
    tong_prompt = input_tokens + ghi_cache_5m + ghi_cache_1h + doc_cache
    if "nguong_prompt_token" in g and tong_prompt > g["nguong_prompt_token"]:
        vao, ra = g["vao_usd_tren_nguong"], g["ra_usd_tren_nguong"]   # áp cho cả request
    usd = (input_tokens * vao
           + ghi_cache_5m * vao * hs["he_so_ghi_cache_5m"]
           + ghi_cache_1h * vao * hs["he_so_ghi_cache_1h"]
           + doc_cache * vao * g["he_so_doc_cache"]
           + output_tokens * ra) / 1_000_000
    if batch:
        usd *= hs["he_so_batch"]                                       # cộng dồn với giảm giá cache
    return round(usd, 8)


def tach_usage(usage) -> dict:
    """Đọc usage (object SDK hoặc dict) thành các số dùng để tính tiền và ghi log."""
    def lay(o, k):
        return (o.get(k) if isinstance(o, dict) else getattr(o, k, None)) or 0
    cc = (usage.get("cache_creation") if isinstance(usage, dict) else getattr(usage, "cache_creation", None)) or {}
    tong_ghi = lay(usage, "cache_creation_input_tokens")
    g5, g1 = lay(cc, "ephemeral_5m_input_tokens"), lay(cc, "ephemeral_1h_input_tokens")
    if not (g5 or g1):
        g5 = tong_ghi                                                  # không có tách TTL: coi là 5 phút
    return {"input_tokens": lay(usage, "input_tokens"), "cache_creation_input_tokens": tong_ghi,
            "ghi_cache_5m": g5, "ghi_cache_1h": g1,
            "cache_read_input_tokens": lay(usage, "cache_read_input_tokens"),
            "output_tokens": lay(usage, "output_tokens")}
