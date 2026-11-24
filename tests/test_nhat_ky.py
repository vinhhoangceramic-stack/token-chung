"""Test ghi log: trường `may` (TOKEN_CHUNG_MAY) và trường `uoc_tinh`. Không gọi mạng, log ghi vào thư mục tạm."""
import json
import os
import socket
import tempfile
import unittest
from types import SimpleNamespace as NS
from unittest import mock

from token_chung import cau_hinh, nhat_ky


class TestNhatKy(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log = os.path.join(self.tmp.name, "usage.jsonl")
        mock.patch.dict(os.environ, {"TOKEN_CHUNG_LOG": self.log}).start()
        os.environ.pop("TOKEN_CHUNG_MAY", None)
        self.addCleanup(mock.patch.stopall)
        self.addCleanup(self.tmp.cleanup)

    def test_may_lay_tu_bien_moi_truong(self):
        os.environ["TOKEN_CHUNG_MAY"] = "may-b"
        self.assertEqual(nhat_ky.ghi_lan_max("du-an-thu")["may"], "may-b")

    def test_may_cat_khoang_trang(self):
        os.environ["TOKEN_CHUNG_MAY"] = "  may-b  "
        self.assertEqual(cau_hinh.ten_may(), "may-b")

    def test_may_khong_dat_hoac_rong_thi_dung_hostname(self):
        self.assertEqual(cau_hinh.ten_may(), socket.gethostname())
        for gia_tri in ("", "   "):
            os.environ["TOKEN_CHUNG_MAY"] = gia_tri
            self.assertEqual(nhat_ky.ghi_lan_max("du-an-thu")["may"], socket.gethostname())

    def test_may_truyen_thang_thang_bien(self):
        os.environ["TOKEN_CHUNG_MAY"] = "may-b"
        self.assertEqual(nhat_ky.ghi(du_an="d", lan="api", may="may-c")["may"], "may-c")

    def test_uoc_tinh_mac_dinh_false(self):
        self.assertIs(nhat_ky.ghi_lan_max("du-an-thu")["uoc_tinh"], False)
        kq = NS(usage={"input_tokens": 1, "output_tokens": 2}, total_cost_usd=0.5)
        d = nhat_ky.ghi_tu_agent_sdk("du-an-thu", kq, model="claude-opus-5-5")
        self.assertIs(d["uoc_tinh"], False)
        self.assertEqual(d["chi_phi_usd"], 0.5)

    def test_uoc_tinh_true_va_dong_ghi_ra_file_co_13_khoa(self):
        nhat_ky.ghi(du_an="d", lan="api", chi_phi_usd=0.1, uoc_tinh=True)
        with open(self.log, encoding="utf-8") as f:
            dong = json.loads(f.readline())
        self.assertEqual(list(dong), list(cau_hinh.TRUONG_LOG))
        self.assertEqual(len(dong), 13)
        self.assertIs(dong["uoc_tinh"], True)


if __name__ == "__main__":
    unittest.main()
