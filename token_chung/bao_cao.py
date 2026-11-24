"""Tổng hợp log theo dự án: `python -m token_chung.bao_cao`.

Mỗi dòng log rơi vào đúng MỘT trong bốn nhóm, không cộng chéo:
- do_that: có chi_phi_usd và uoc_tinh false (giá có trong bảng, hoặc do SDK đo).
- uoc_tinh: chi_phi_usd tính theo giá dự phòng (uoc_tinh true). Chỉ là ước tính, không trộn với phần đo thật.
- chua_co_gia: chi_phi_usd rỗng và không phải lan "max" (model lạ ở v0.1.0 và v0.1.1). Chỉ đếm lời gọi và token,
  không có USD, và KHÔNG nằm trong mẫu số của "do_that".
- lan_max: chạy bằng Claude Code (gói Max), không có chi phí theo lời gọi.
Dòng cũ 12 trường (không có uoc_tinh) coi là uoc_tinh false.

Từ v0.1.2 khóa cũ `chi_phi_usd_moi_loi_goi` đã bị BỎ (đổi tên thành do_that.chi_phi_usd_trung_binh_moi_loi_goi
và uoc_tinh.chi_phi_usd_trung_binh_moi_loi_goi), để người đọc cũ lỗi to thay vì lệch nghĩa trong im lặng.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict

from . import cau_hinh

_TOKEN = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")


def _moi_nhom() -> dict:
    return {"so_loi_goi": 0, "vao": 0, "ghi": 0, "doc": 0,
            "do_that": [0, 0.0], "uoc_tinh": [0, 0.0], "chua_co_gia": {"so_loi_goi": 0, **{k: 0 for k in _TOKEN}},
            "lan_max": 0, "ly_do": Counter(), "lan": set(), "may": set()}


def _khoi_tien(n_tien: list) -> dict:
    n, tong = n_tien
    return {"so_loi_goi": n, "chi_phi_usd_tong": round(tong, 8),
            "chi_phi_usd_trung_binh_moi_loi_goi": round(tong / n, 6) if n else None}


def tong_hop(duong_dan=None) -> dict:
    p = duong_dan or cau_hinh.duong_dan_log()
    nhom = defaultdict(_moi_nhom)
    if not p.exists():
        return {}
    for dong in p.read_text(encoding="utf-8").splitlines():
        if not dong.strip():
            continue
        d = json.loads(dong)
        g = nhom[d["du_an"]]
        g["so_loi_goi"] += 1
        g["vao"] += d.get("input_tokens") or 0
        g["ghi"] += d.get("cache_creation_input_tokens") or 0
        g["doc"] += d.get("cache_read_input_tokens") or 0
        tien = d.get("chi_phi_usd")
        if tien is not None:
            kieu = "uoc_tinh" if (d.get("uoc_tinh") or False) else "do_that"
            g[kieu][0] += 1
            g[kieu][1] += tien
        elif d.get("lan") == "max":
            g["lan_max"] += 1
        else:
            c = g["chua_co_gia"]
            c["so_loi_goi"] += 1
            for k in _TOKEN:
                c[k] += d.get(k) or 0
        if d.get("cache_miss_reason"):
            g["ly_do"][d["cache_miss_reason"]] += 1
        g["lan"].add(d.get("lan"))
        g["may"].add(d.get("may"))
    kq = {}
    for du_an, g in nhom.items():
        tong = g["vao"] + g["ghi"] + g["doc"]
        kq[du_an] = {"so_loi_goi": g["so_loi_goi"], "lan": sorted(x for x in g["lan"] if x),
                     "may": sorted(x for x in g["may"] if x),
                     "ty_le_cache_read": round(g["doc"] / tong, 4) if tong else None,
                     "do_that": _khoi_tien(g["do_that"]),
                     "uoc_tinh": _khoi_tien(g["uoc_tinh"]),
                     "chua_co_gia": g["chua_co_gia"],
                     "lan_max": {"so_loi_goi": g["lan_max"]},
                     "cache_miss_reason_pho_bien": g["ly_do"].most_common(1)[0][0] if g["ly_do"] else None}
    return kq


if __name__ == "__main__":
    for du_an, v in tong_hop().items():
        print(du_an, json.dumps(v, ensure_ascii=False))
