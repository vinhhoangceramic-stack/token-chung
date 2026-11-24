"""Phien: một phiên gọi Messages API qua token-chung.

Quy tắc giữ cache:
- Thứ tự prompt cố định: tools, rồi system, rồi messages. Một điểm cache ở cuối phần tĩnh,
  cộng điểm cache tự động cho phần đuôi hội thoại. Tối đa 4 điểm.
- tools, system, thinking, effort cấp request, model chốt khi tạo phiên; không có cách đổi giữa phiên.
  Muốn đổi effort cho từng lượt: dùng tin_nhan_doi_effort() (message role "system"), không mất cache.
- Mỗi lượt gửi diagnostics.previous_message_id; ghi cache_miss_reason vào log.
"""
from __future__ import annotations

import logging
import time
from collections import deque

from . import cau_hinh, gia, nhat_ky, phan_tinh

_log = logging.getLogger("token_chung")

_THAM_SO_CAM = {"model", "tools", "system", "thinking", "output_config", "cache_control", "diagnostics",
                "betas", "max_tokens", "stream", "speed", "inference_geo"}
_EFFORT = ("low", "medium", "high", "xhigh", "max")


def tin_nhan_doi_effort(muc: str) -> dict:
    """Message chỉ đổi effort cho các lượt sau, không làm mất cache (cần model hỗ trợ effort theo message)."""
    if muc not in _EFFORT:
        raise ValueError(f"effort phải thuộc {_EFFORT}")
    return {"role": "system", "content": [], "output_config": {"effort": muc}}


def chon_ttl(khoang_nghi_giay) -> str:
    """1 giờ nếu có ít nhất 1 trong 20 khoảng nghỉ gần nhất rơi vào 5–60 phút; ngược lại 5 phút."""
    gan = list(khoang_nghi_giay)[-20:]
    return "1h" if any(300 <= k <= 3600 for k in gan) else "5m"


class Phien:
    def __init__(self, du_an: str, model: str, *, system=None, tools=None, effort: str | None = None,
                 thinking: dict | None = None, ttl: str = "5m", max_tokens: int = 64_000,
                 task_budget: int | None = None, context_management: dict | None = None,
                 dinh_dang: dict | None = None, cache_hoi_thoai: bool = True,
                 betas: tuple[str, ...] = (), lan: str = "api", client=None):
        """dinh_dang: output_config.format (structured output), chốt cho cả phiên.
        cache_hoi_thoai: đặt điểm cache tự động cho đuôi hội thoại. Tắt (False) cho lời gọi một lượt
        có nội dung khác nhau mỗi lần: điểm đó chỉ ghi cache mà không bao giờ được đọc lại (phí thừa)."""
        if thinking is not None and thinking.get("type") != "adaptive":
            raise ValueError("Chỉ nhận thinking={'type': 'adaptive'} hoặc bỏ trống. Không gửi thinking disabled, "
                             "không dùng budget_tokens; giảm suy nghĩ bằng effort.")
        if effort is not None and effort not in _EFFORT:
            raise ValueError(f"effort phải thuộc {_EFFORT}")
        if ttl not in ("5m", "1h", "tu_dong"):
            raise ValueError("ttl phải là '5m', '1h' hoặc 'tu_dong'")
        if max_tokens <= 0:
            raise ValueError("max_tokens phải > 0 (đây là trần chống chạy quá, không phải công cụ tiết kiệm)")
        if task_budget is not None and task_budget < cau_hinh.NGAN_SACH_VIEC_TOI_THIEU:
            raise ValueError(f"task_budget tối thiểu {cau_hinh.NGAN_SACH_VIEC_TOI_THIEU}")
        self.du_an, self.model, self.lan = du_an, model, lan
        self._tools_goc, self._system_goc = tools, system
        self._effort, self._thinking, self._ttl = effort, thinking, ttl
        self._max_tokens, self._task_budget, self._ctx = max_tokens, task_budget, context_management
        self._dinh_dang, self._cache_hoi_thoai = dinh_dang, cache_hoi_thoai
        self._betas = [cau_hinh.BETA_CHAN_DOAN_CACHE, *betas]
        if task_budget is not None:
            self._betas.append(cau_hinh.BETA_NGAN_SACH_VIEC)
        if context_management is not None and cau_hinh.BETA_SUA_NGU_CANH not in self._betas:
            self._betas.append(cau_hinh.BETA_SUA_NGU_CANH)
        self._client = client
        self._id_truoc: str | None = None
        self._bat_dau_truoc: float | None = None
        self.khoang_nghi = deque(maxlen=20)

    # ---- chỉ đọc ----
    @property
    def ttl_hien_tai(self) -> str:
        return chon_ttl(self.khoang_nghi) if self._ttl == "tu_dong" else self._ttl

    def _khach(self):
        if self._client is None:
            import anthropic                      # khóa đọc từ ANTHROPIC_API_KEY trong môi trường của app
            self._client = anthropic.Anthropic()
        return self._client

    def dung_yeu_cau(self, messages: list) -> dict:
        ttl = self.ttl_hien_tai
        tools, system = phan_tinh.dung(self._tools_goc, self._system_goc, ttl)
        co_tu_dong = self._cache_hoi_thoai and (phan_tinh.dem_diem_cache(messages)
                                                + phan_tinh.dem_diem_cache(tools, system)
                                                < cau_hinh.SO_DIEM_CACHE_TOI_DA)
        phan_tinh.kiem_so_diem(tools, system, messages, co_tu_dong)
        betas = list(self._betas)
        if any(isinstance(m, dict) and m.get("role") == "system" and m.get("output_config") for m in messages):
            betas.append(cau_hinh.BETA_EFFORT_THEO_MESSAGE)
        yc: dict = {"model": self.model, "max_tokens": self._max_tokens}
        if tools:
            yc["tools"] = tools
        if system:
            yc["system"] = system
        yc["messages"] = messages
        oc = {}
        if self._effort:
            oc["effort"] = self._effort
        if self._task_budget:
            oc["task_budget"] = {"type": "tokens", "total": self._task_budget}
        if self._dinh_dang:
            oc["format"] = self._dinh_dang
        if oc:
            yc["output_config"] = oc
        if self._thinking:
            yc["thinking"] = dict(self._thinking)
        if self._ctx:
            yc["context_management"] = self._ctx
        if co_tu_dong:
            yc["cache_control"] = phan_tinh.dau_cache(ttl)        # điểm tự động cho đuôi hội thoại
        yc["diagnostics"] = {"previous_message_id": self._id_truoc}
        yc["betas"] = sorted(set(betas))
        return yc

    def effort_hien_tai(self, messages: list) -> str | None:
        for m in reversed(messages):
            if isinstance(m, dict) and m.get("role") == "system" and (m.get("output_config") or {}).get("effort"):
                return m["output_config"]["effort"]
        return self._effort

    def goi(self, messages: list, **them):
        """Gửi một lượt. Trả message của SDK; người gọi tự nối response.content vào messages."""
        cam = _THAM_SO_CAM & set(them)
        if cam:
            raise ValueError(f"Không đổi {sorted(cam)} giữa phiên: tạo Phien mới nếu thật cần.")
        bd = time.time()
        if self._bat_dau_truoc is not None:
            self.khoang_nghi.append(bd - self._bat_dau_truoc)
        self._bat_dau_truoc = bd
        yc = {**self.dung_yeu_cau(messages), **them}
        with self._khach().beta.messages.stream(**yc) as luong:
            tl = luong.get_final_message()
        self._id_truoc = tl.id
        self.dong_log_cuoi = self._ghi_log(tl, self.effort_hien_tai(messages))
        return tl

    def _ghi_log(self, tl, effort) -> dict | None:
        """Tính tiền và ghi log. Lỗi ở đây chỉ được cảnh báo, KHÔNG làm hỏng lời gọi API đã thành công."""
        try:
            u = gia.tach_usage(tl.usage)
            chan_doan = getattr(tl, "diagnostics", None)
            ly_do = getattr(getattr(chan_doan, "cache_miss_reason", None), "type", None)
            tien, uoc = None, False
            if self.lan != "max":
                tien, uoc = gia.tinh_chi_phi_du_phong(self.model, u["input_tokens"], u["ghi_cache_5m"], u["ghi_cache_1h"],
                                                      u["cache_read_input_tokens"], u["output_tokens"])
            return nhat_ky.ghi(du_an=self.du_an, model=self.model, effort=effort, lan=self.lan,
                               input_tokens=u["input_tokens"],
                               cache_creation_input_tokens=u["cache_creation_input_tokens"],
                               cache_read_input_tokens=u["cache_read_input_tokens"],
                               output_tokens=u["output_tokens"], chi_phi_usd=tien, cache_miss_reason=ly_do,
                               uoc_tinh=uoc)
        except Exception:                                   # noqa: BLE001 - log không được làm hỏng lời gọi
            _log.exception("token-chung: không ghi được log usage")
            return None
