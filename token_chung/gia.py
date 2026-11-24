"""Tính chi_phi_usd từ gia_model.json (file giá duy nhất).

Giá vào/ra trong file là USD cho 1 triệu token. Mọi khóa he_so_* là hệ số nhân với giá vào của chính model.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from importlib import resources

_log = logging.getLogger("token_chung")


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


def gia_du_phong() -> dict | None:
    """Giá dự phòng cho model chưa có trong bảng: TỪNG THÀNH PHẦN lấy giá lớn nhất trong các model đã biết.

    Không nhân "giá cao nhất" với "hệ số cao nhất". Riêng đọc cache là max của từng (giá vào x he_so_doc_cache)
    tính cho mỗi model. Cả giá thường lẫn giá trên ngưỡng prompt đều là ứng viên. Trả None nếu bảng không có model nào.
    `nguon` ghi model cho ra giá lớn nhất của từng thành phần, để đối chiếu tay.
    """
    bg = bang_gia()
    if not bg["model"]:
        return None
    hs = bg["he_so_chung"]
    vao, ra, doc = [], [], []
    for ten, g in bg["model"].items():
        for v in (g["vao_usd"], g.get("vao_usd_tren_nguong")):
            if v is not None:
                vao.append((v, ten))
                doc.append((v * g["he_so_doc_cache"], ten))
        ra += [(r, ten) for r in (g["ra_usd"], g.get("ra_usd_tren_nguong")) if r is not None]
    ghi5 = [(v * hs["he_so_ghi_cache_5m"], ten) for v, ten in vao]
    ghi1 = [(v * hs["he_so_ghi_cache_1h"], ten) for v, ten in vao]
    lon = {k: max(ds, key=lambda x: x[0]) for k, ds in
           {"vao_usd": vao, "ra_usd": ra, "doc_cache_usd": doc, "ghi_cache_5m_usd": ghi5, "ghi_cache_1h_usd": ghi1}.items()}
    kq = {k: v[0] for k, v in lon.items()}
    kq["he_so_batch"] = hs["he_so_batch"]
    kq["nguon"] = {k: v[1] for k, v in lon.items()}
    return kq


def tinh_chi_phi_du_phong(model: str, input_tokens: int = 0, ghi_cache_5m: int = 0, ghi_cache_1h: int = 0,
                          doc_cache: int = 0, output_tokens: int = 0, batch: bool = False) -> tuple[float | None, bool]:
    """Trả (usd, uoc_tinh). Model có giá: (giá thật, False). Model chưa có: (giá dự phòng, True) kèm WARNING.
    Bảng giá rỗng: (None, False)."""
    usd = tinh_chi_phi(model, input_tokens, ghi_cache_5m, ghi_cache_1h, doc_cache, output_tokens, batch)
    if usd is not None:
        return usd, False
    dp = gia_du_phong()
    if dp is None:
        _log.error("token-chung: bảng giá rỗng, không tính được chi_phi_usd cho model %s", model)
        return None, False
    usd = (input_tokens * dp["vao_usd"] + ghi_cache_5m * dp["ghi_cache_5m_usd"] + ghi_cache_1h * dp["ghi_cache_1h_usd"]
           + doc_cache * dp["doc_cache_usd"] + output_tokens * dp["ra_usd"]) / 1_000_000
    if batch:
        usd *= dp["he_so_batch"]
    _log.warning("token-chung: model %s chưa có trong gia_model.json; chi_phi_usd tính theo GIÁ DỰ PHÒNG "
                 "(USD/triệu token, mỗi thành phần lấy giá lớn nhất trong bảng: vào %s, ra %s, đọc cache %s, "
                 "ghi cache 5m %s, ghi cache 1h %s, batch x%s); dòng log đánh dấu uoc_tinh=true",
                 model, dp["vao_usd"], dp["ra_usd"], dp["doc_cache_usd"], dp["ghi_cache_5m_usd"],
                 dp["ghi_cache_1h_usd"], dp["he_so_batch"])
    return round(usd, 8), True
