"""Test báo cáo: tách đo thật / ước tính / chưa có giá. Không gọi mạng, log ghi vào thư mục tạm."""
import json
import tempfile
import unittest
from pathlib import Path

from token_chung import bao_cao

_TRONG = dict(model=None, effort=None, input_tokens=None, cache_creation_input_tokens=None,
              cache_read_input_tokens=None, output_tokens=None, chi_phi_usd=None, thoi_diem="t",
              cache_miss_reason=None, may="m", lan="api")


def _dong(du_an, co_uoc_tinh=True, **kw):
    d = {"du_an": du_an, **_TRONG, **kw}
    if co_uoc_tinh:
        d.setdefault("uoc_tinh", False)
    else:
        d.pop("uoc_tinh", None)                              # dòng cũ 12 trường
    return d


class TestBaoCao(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Path(self.tmp.name) / "usage.jsonl"

    def _ghi(self, dong):
        self.p.write_text("\n".join(json.dumps(d) for d in dong) + "\n", encoding="utf-8")
        return bao_cao.tong_hop(self.p)

    def test_dong_cu_12_truong_chi_phi_rong_khong_vao_mau_so_do_that(self):
        kq = self._ghi([
            _dong("a", False, input_tokens=100, output_tokens=10, chi_phi_usd=0.02),                  # cũ, có tiền
            _dong("a", False, model="model-la", input_tokens=700, cache_creation_input_tokens=30,
                  cache_read_input_tokens=200, output_tokens=50),                                     # cũ, model lạ: tiền rỗng
        ])["a"]
        self.assertEqual(kq["do_that"]["so_loi_goi"], 1)
        self.assertAlmostEqual(kq["do_that"]["chi_phi_usd_trung_binh_moi_loi_goi"], 0.02)           # không phải 0.01
        self.assertEqual(kq["chua_co_gia"], {"so_loi_goi": 1, "input_tokens": 700,
                                             "cache_creation_input_tokens": 30, "cache_read_input_tokens": 200,
                                             "output_tokens": 50})
        self.assertNotIn("chi_phi_usd_tong", kq["chua_co_gia"])                                       # không có USD

    def test_tach_do_that_uoc_tinh_chua_co_gia_lan_max(self):
        kq = self._ghi([
            _dong("a", False, chi_phi_usd=0.01),                                                      # cũ 12 trường = đo thật
            _dong("a", chi_phi_usd=0.03),
            _dong("a", chi_phi_usd=0.5, uoc_tinh=True),
            _dong("a", False, input_tokens=5),                                                        # chưa có giá
            _dong("a", lan="max"),                                                                    # Claude Code
            _dong("a", chi_phi_usd=0.2, lan="api", model="claude-opus-5-5"),                          # SDK/đo thật
        ])["a"]
        self.assertEqual(kq["so_loi_goi"], 6)
        self.assertEqual(kq["do_that"]["so_loi_goi"], 3)
        self.assertAlmostEqual(kq["do_that"]["chi_phi_usd_tong"], 0.24)
        self.assertAlmostEqual(kq["do_that"]["chi_phi_usd_trung_binh_moi_loi_goi"], 0.08)
        self.assertEqual(kq["uoc_tinh"]["so_loi_goi"], 1)
        self.assertAlmostEqual(kq["uoc_tinh"]["chi_phi_usd_tong"], 0.5)
        self.assertEqual(kq["chua_co_gia"]["so_loi_goi"], 1)
        self.assertEqual(kq["lan_max"]["so_loi_goi"], 1)
        tong_nhom = (kq["do_that"]["so_loi_goi"] + kq["uoc_tinh"]["so_loi_goi"]
                     + kq["chua_co_gia"]["so_loi_goi"] + kq["lan_max"]["so_loi_goi"])
        self.assertEqual(tong_nhom, kq["so_loi_goi"])                                                 # mỗi dòng đúng một nhóm

    def test_khoa_cu_da_bi_bo_de_nguoi_doc_cu_loi_to(self):
        kq = self._ghi([_dong("a", chi_phi_usd=0.03)])["a"]
        self.assertNotIn("chi_phi_usd_moi_loi_goi", kq)
        with self.assertRaises(KeyError):
            kq["chi_phi_usd_moi_loi_goi"]

    def test_khong_co_file_thi_rong(self):
        self.assertEqual(bao_cao.tong_hop(Path(self.tmp.name) / "khong_co.jsonl"), {})


if __name__ == "__main__":
    unittest.main()
