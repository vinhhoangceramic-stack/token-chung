"""Tổng hợp log theo dự án: `python -m token_chung.bao_cao`."""
from __future__ import annotations

import json
from collections import Counter, defaultdict

from . import cau_hinh


def tong_hop(duong_dan=None) -> dict:
    p = duong_dan or cau_hinh.duong_dan_log()
    nhom = defaultdict(lambda: {"so_loi_goi": 0, "vao": 0, "ghi": 0, "doc": 0, "tien": 0.0, "co_tien": 0,
                                "ly_do": Counter(), "lan": set(), "may": set()})
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
        if d.get("chi_phi_usd") is not None:
            g["tien"] += d["chi_phi_usd"]
            g["co_tien"] += 1
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
                     "chi_phi_usd_moi_loi_goi": round(g["tien"] / g["co_tien"], 6) if g["co_tien"] else None,
                     "cache_miss_reason_pho_bien": g["ly_do"].most_common(1)[0][0] if g["ly_do"] else None}
    return kq


if __name__ == "__main__":
    for du_an, v in tong_hop().items():
        print(du_an, json.dumps(v, ensure_ascii=False))
