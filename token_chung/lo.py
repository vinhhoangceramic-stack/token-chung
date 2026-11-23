"""Batch API (giảm 50%): mọi request trong một lô dùng cùng khối tĩnh và cùng cache_control TTL 1 giờ."""
from __future__ import annotations

import logging

from . import gia, nhat_ky, phan_tinh

_log = logging.getLogger("token_chung")

TTL_LO = "1h"


def dung_lo(model: str, viec: list[tuple[str, list]], *, system=None, tools=None,
            effort: str | None = None, max_tokens: int = 16_000) -> list[dict]:
    """viec: danh sách (custom_id, messages). Trả danh sách request cho batches.create."""
    if max_tokens <= 0:
        raise ValueError("Batch không dùng max_tokens <= 0")
    t, s = phan_tinh.dung(tools, system, TTL_LO)
    ds = []
    for cid, messages in viec:
        phan_tinh.kiem_so_diem(t, s, messages, co_tu_dong=False)
        p: dict = {"model": model, "max_tokens": max_tokens}
        if t:
            p["tools"] = t
        if s:
            p["system"] = s
        p["messages"] = messages
        if effort:
            p["output_config"] = {"effort": effort}
        ds.append({"custom_id": cid, "params": p})
    return ds


def gui_lo(client, model: str, viec: list[tuple[str, list]], **kw) -> str:
    """Tạo lô, trả batch id. Kết quả đọc sau bằng doc_ket_qua()."""
    return client.messages.batches.create(requests=dung_lo(model, viec, **kw)).id


def doc_ket_qua(client, batch_id: str, du_an: str, *, effort: str | None = None):
    """Đọc kết quả lô (thứ tự bất kỳ, khóa theo custom_id), ghi log từng request thành công, trả về từng kết quả."""
    for r in client.messages.batches.results(batch_id):
        if r.result.type == "succeeded":
            try:                                            # lỗi tính tiền/ghi log không làm hỏng việc đọc kết quả
                m = r.result.message
                u = gia.tach_usage(m.usage)
                tien = gia.tinh_chi_phi(m.model, u["input_tokens"], u["ghi_cache_5m"], u["ghi_cache_1h"],
                                        u["cache_read_input_tokens"], u["output_tokens"], batch=True)
                if tien is None:
                    _log.error("token-chung: model %s không có trong gia_model.json, chi_phi_usd để trống", m.model)
                nhat_ky.ghi(du_an=du_an, model=m.model, effort=effort, lan="api",
                            input_tokens=u["input_tokens"],
                            cache_creation_input_tokens=u["cache_creation_input_tokens"],
                            cache_read_input_tokens=u["cache_read_input_tokens"], output_tokens=u["output_tokens"],
                            chi_phi_usd=tien)
            except Exception:                               # noqa: BLE001
                _log.exception("token-chung: không ghi được log usage cho %s", r.custom_id)
        yield r
