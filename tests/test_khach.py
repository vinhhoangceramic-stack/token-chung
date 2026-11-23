"""Test wrapper bằng client giả: không gọi mạng, log ghi vào thư mục tạm (không ghi vào repo)."""
import json
import os
import tempfile
import unittest
from types import SimpleNamespace as NS

from token_chung import Phien, chon_ttl, lo, nhat_ky, tin_nhan_doi_effort
from token_chung import cau_hinh


class _Luong:
    def __init__(self, tl):
        self.tl = tl

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return self.tl


class KhachGia:
    def __init__(self):
        self.yeu_cau = []
        self.dem = 0
        self.beta = NS(messages=NS(stream=self._stream))

    def _stream(self, **yc):
        self.yeu_cau.append(yc)
        self.dem += 1
        ly_do = NS(type="system_changed") if self.dem == 2 else None
        return _Luong(NS(id=f"msg_{self.dem}", content=[], diagnostics=NS(cache_miss_reason=ly_do),
                         usage=NS(input_tokens=100, cache_creation_input_tokens=1000, cache_read_input_tokens=5000,
                                  output_tokens=200, cache_creation=NS(ephemeral_5m_input_tokens=1000,
                                                                       ephemeral_1h_input_tokens=0))))


class TestPhien(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["TOKEN_CHUNG_LOG"] = os.path.join(self.tmp.name, "usage.jsonl")

    def tearDown(self):
        os.environ.pop("TOKEN_CHUNG_LOG", None)
        self.tmp.cleanup()

    def _doc_log(self):
        with open(os.environ["TOKEN_CHUNG_LOG"], encoding="utf-8") as f:
            return [json.loads(d) for d in f]

    def test_thu_tu_cache_va_diagnostics(self):
        k = KhachGia()
        p = Phien("du-an-thu", "claude-opus-5-5", system="He thong", tools=[{"name": "a"}, {"name": "b"}],
                  effort="low", client=k)
        p.goi([{"role": "user", "content": "x"}])
        p.goi([{"role": "user", "content": "y"}])
        yc1, yc2 = k.yeu_cau
        self.assertEqual(list(yc1)[:5], ["model", "max_tokens", "tools", "system", "messages"])
        self.assertEqual(yc1["system"][-1]["cache_control"], {"type": "ephemeral"})
        self.assertNotIn("cache_control", yc1["tools"][-1])          # điểm trên system đã phủ tools
        self.assertEqual(yc1["cache_control"], {"type": "ephemeral"})  # điểm tự động cho đuôi
        self.assertEqual(yc1["diagnostics"], {"previous_message_id": None})
        self.assertEqual(yc2["diagnostics"], {"previous_message_id": "msg_1"})
        self.assertIn(cau_hinh.BETA_CHAN_DOAN_CACHE, yc1["betas"])
        self.assertNotIn("thinking", yc1)
        self.assertEqual(yc1["output_config"], {"effort": "low"})
        log = self._doc_log()
        self.assertEqual(len(log), 2)
        self.assertEqual(list(log[0]), list(cau_hinh.TRUONG_LOG))
        self.assertIsNone(log[0]["cache_miss_reason"])
        self.assertEqual(log[1]["cache_miss_reason"], "system_changed")
        # 100*4 + 1000*4*1.25 + 5000*4*0.05 + 200*20 = 400+5000+1000+4000 = 10400 / 1e6
        self.assertAlmostEqual(log[0]["chi_phi_usd"], 0.0104, places=8)
        print(f"\nlog mau: chi_phi_usd = {log[0]['chi_phi_usd']} USD (doi chieu: 0.0104)")

    def test_cam_doi_giua_phien(self):
        p = Phien("du-an-thu", "claude-opus-5-5", client=KhachGia())
        for k in ("tools", "system", "thinking", "model", "output_config"):
            with self.assertRaises(ValueError):
                p.goi([{"role": "user", "content": "x"}], **{k: None})
        with self.assertRaises(ValueError):
            Phien("d", "claude-opus-5-5", thinking={"type": "disabled"})
        with self.assertRaises(ValueError):
            Phien("d", "claude-opus-5-5", thinking={"type": "enabled", "budget_tokens": 2000})
        with self.assertRaises(ValueError):
            Phien("d", "claude-opus-5-5", task_budget=10_000)

    def test_doi_effort_theo_message(self):
        k = KhachGia()
        p = Phien("du-an-thu", "claude-opus-5-5", effort="low", client=k)
        p.goi([{"role": "user", "content": "x"}, tin_nhan_doi_effort("high")])
        self.assertIn(cau_hinh.BETA_EFFORT_THEO_MESSAGE, k.yeu_cau[0]["betas"])
        self.assertEqual(k.yeu_cau[0]["output_config"], {"effort": "low"})   # cấp request không đổi
        self.assertEqual(self._doc_log()[0]["effort"], "high")

    def test_ttl(self):
        self.assertEqual(chon_ttl([10, 20, 30]), "5m")
        self.assertEqual(chon_ttl([10] * 19 + [600]), "1h")
        self.assertEqual(chon_ttl([600] + [10] * 20), "5m")     # chỉ xét 20 khoảng gần nhất
        self.assertEqual(chon_ttl([4000]), "5m")                # trên 60 phút: không giúp

    def test_lo_ttl_1h(self):
        ds = lo.dung_lo("claude-haiku-5-5", [("a", [{"role": "user", "content": "x"}])], system="S", effort="low")
        self.assertEqual(ds[0]["params"]["system"][-1]["cache_control"], {"type": "ephemeral", "ttl": "1h"})
        with self.assertRaises(ValueError):
            lo.dung_lo("claude-haiku-5-5", [("a", [])], max_tokens=0)

    def test_dinh_dang_va_tat_cache_hoi_thoai(self):
        k = KhachGia()
        sch = {"type": "json_schema", "schema": {"type": "object"}}
        p = Phien("du-an-thu", "claude-haiku-5-5", dinh_dang=sch, effort="low", max_tokens=300,
                  cache_hoi_thoai=False, client=k)
        p.goi([{"role": "user", "content": "x"}])
        yc = k.yeu_cau[0]
        self.assertEqual(yc["output_config"], {"effort": "low", "format": sch})
        self.assertNotIn("cache_control", yc)                # không có điểm cache tự động
        self.assertNotIn("system", yc)
        self.assertNotIn("tools", yc)
        self.assertEqual(yc["max_tokens"], 300)

    def test_model_khong_co_gia_khong_lam_hong_loi_goi(self):
        k = KhachGia()
        p = Phien("du-an-thu", "model-chua-co-gia", client=k)
        with self.assertLogs("token_chung", level="ERROR") as cb:
            tl = p.goi([{"role": "user", "content": "x"}])
        self.assertEqual(tl.id, "msg_1")                      # lời gọi vẫn trả kết quả
        self.assertIsNone(self._doc_log()[0]["chi_phi_usd"])
        self.assertTrue(any("model-chua-co-gia" in d for d in cb.output))

    def test_loi_ghi_log_khong_lam_hong_loi_goi(self):
        os.environ["TOKEN_CHUNG_LOG"] = self.tmp.name          # là thư mục, không mở như file được
        k = KhachGia()
        p = Phien("du-an-thu", "claude-haiku-5-5", client=k)
        with self.assertLogs("token_chung", level="ERROR"):
            tl = p.goi([{"role": "user", "content": "x"}])
        self.assertEqual(tl.id, "msg_1")
        self.assertIsNone(p.dong_log_cuoi)

    def test_lan_max(self):
        d = nhat_ky.ghi_lan_max("du-an-thu")
        self.assertEqual(d["lan"], "max")
        self.assertIsNone(d["chi_phi_usd"])
        self.assertTrue(d["may"] and d["thoi_diem"])


if __name__ == "__main__":
    unittest.main()
