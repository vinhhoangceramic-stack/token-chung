"""Test tính tiền: chạy `python -m unittest -v tests.test_gia` ở thư mục gốc repo. Không gọi mạng."""
import unittest
from unittest import mock

from token_chung.gia import gia_du_phong, tinh_chi_phi, tinh_chi_phi_du_phong


class TestGia(unittest.TestCase):
    def test_loi_goi_mau_co_doc_cache(self):
        # Opus 5.5: 1 triệu token đọc cache phải ra 0.20 USD (4.0 x 0.05)
        chi_doc = tinh_chi_phi("claude-opus-5-5", doc_cache=1_000_000)
        print(f"\nOpus 5.5, 1.000.000 token doc cache        = {chi_doc} USD (doi chieu: 0.20)")
        self.assertAlmostEqual(chi_doc, 0.20, places=8)

        # Lời gọi mẫu: 2.000 vào thường + 10.000 ghi cache 5m + 50.000 đọc cache + 1.000 ra
        # = 2000*4 + 10000*4*1.25 + 50000*4*0.05 + 1000*20 = 8000 + 50000 + 10000 + 20000 = 88000 / 1e6
        mau = tinh_chi_phi("claude-opus-5-5", input_tokens=2_000, ghi_cache_5m=10_000,
                           doc_cache=50_000, output_tokens=1_000)
        print(f"Opus 5.5, loi goi mau (2k vao, 10k ghi 5m, 50k doc, 1k ra) = {mau} USD (doi chieu: 0.088)")
        self.assertAlmostEqual(mau, 0.088, places=8)

        # Cùng lời gọi mẫu chạy batch: giảm 50%, cộng dồn với cache
        mau_lo = tinh_chi_phi("claude-opus-5-5", input_tokens=2_000, ghi_cache_5m=10_000,
                              doc_cache=50_000, output_tokens=1_000, batch=True)
        print(f"Opus 5.5, cung loi goi mau, batch          = {mau_lo} USD (doi chieu: 0.044)")
        self.assertAlmostEqual(mau_lo, 0.044, places=8)

        # Đối chiếu các model còn lại: 1 triệu token đọc cache
        for model, mong in [("claude-sonnet-5-5", 0.10), ("claude-fable-5-2", 0.20)]:
            v = tinh_chi_phi(model, doc_cache=1_000_000)
            print(f"{model}, 1.000.000 token doc cache = {v} USD (doi chieu: {mong})")
            self.assertAlmostEqual(v, mong, places=8)
        # Haiku: dưới ngưỡng 100K (dùng 100.000 token đúng ngưỡng) và trên ngưỡng
        h_duoi = tinh_chi_phi("claude-haiku-5-5", doc_cache=100_000)
        h_tren = tinh_chi_phi("claude-haiku-5-5", doc_cache=1_000_000)
        print(f"claude-haiku-5-5, 100.000 token doc cache (<=100K) = {h_duoi} USD (doi chieu: 0.001 = 0.01/trieu)")
        print(f"claude-haiku-5-5, 1.000.000 token doc cache (>100K) = {h_tren} USD (doi chieu: 0.05)")
        self.assertAlmostEqual(h_duoi, 0.001, places=8)
        self.assertAlmostEqual(h_tren, 0.05, places=8)

    def test_model_la_khong_doan(self):
        self.assertIsNone(tinh_chi_phi("model-khong-co", input_tokens=1))


class TestGiaDuPhong(unittest.TestCase):
    def test_tung_thanh_phan_lay_gia_lon_nhat(self):
        dp = gia_du_phong()
        for khoa, mong in [("vao_usd", 8.0), ("ra_usd", 40.0), ("doc_cache_usd", 0.2),
                           ("ghi_cache_5m_usd", 10.0), ("ghi_cache_1h_usd", 16.0), ("he_so_batch", 0.5)]:
            self.assertAlmostEqual(dp[khoa], mong, places=8, msg=khoa)
        self.assertEqual(dp["nguon"]["vao_usd"], "claude-fable-5-2")
        self.assertEqual(dp["nguon"]["ra_usd"], "claude-fable-5-2")
        self.assertIn(dp["nguon"]["doc_cache_usd"], ("claude-opus-5-5", "claude-fable-5-2"))
        print("\ngia du phong (USD/trieu): " + ", ".join(f"{k}={dp[k]}" for k in dp if k != "nguon"))

    def test_doc_cache_khong_nhan_gia_cao_nhat_voi_he_so_cao_nhat(self):
        # Cách bị loại: 8.0 (vào cao nhất) x 0.1 (hệ số cao nhất) = 0.8. Cách đúng: max của từng (vào x hệ số) = 0.2
        self.assertAlmostEqual(gia_du_phong()["doc_cache_usd"], 0.2, places=8)
        self.assertNotAlmostEqual(gia_du_phong()["doc_cache_usd"], 0.8, places=3)

    def test_vi_du_tay(self):
        # 1000*8 + 500*10 + 2000*0.2 + 300*40 = 8000 + 5000 + 400 + 12000 = 25400 / 1e6
        usd, uoc = tinh_chi_phi_du_phong("model-la", 1000, 500, 0, 2000, 300)
        self.assertAlmostEqual(usd, 0.0254, places=8)
        self.assertTrue(uoc)
        usd_lo, uoc_lo = tinh_chi_phi_du_phong("model-la", 1000, 500, 0, 2000, 300, batch=True)
        self.assertAlmostEqual(usd_lo, 0.0127, places=8)
        self.assertTrue(uoc_lo)
        usd_1h, _ = tinh_chi_phi_du_phong("model-la", ghi_cache_1h=1_000_000)
        self.assertAlmostEqual(usd_1h, 16.0, places=8)

    def test_model_co_gia_khong_phai_uoc_tinh(self):
        usd, uoc = tinh_chi_phi_du_phong("claude-opus-5-5", 2_000, 10_000, 0, 50_000, 1_000)
        self.assertAlmostEqual(usd, tinh_chi_phi("claude-opus-5-5", 2_000, 10_000, 0, 50_000, 1_000), places=8)
        self.assertFalse(uoc)

    def test_ghi_warning_khi_dung_gia_du_phong(self):
        with self.assertLogs("token_chung", level="WARNING") as cb:
            tinh_chi_phi_du_phong("model-la", input_tokens=1)
        self.assertTrue(any("model-la" in d for d in cb.output))

    def test_bang_gia_rong(self):
        bang = {"he_so_chung": {"he_so_ghi_cache_5m": 1.25, "he_so_ghi_cache_1h": 2.0, "he_so_batch": 0.5}, "model": {}}
        with mock.patch("token_chung.gia.bang_gia", return_value=bang):
            with self.assertLogs("token_chung", level="ERROR"):
                self.assertEqual(tinh_chi_phi_du_phong("model-la", input_tokens=1), (None, False))

    def test_moi_thanh_phan_co_the_den_tu_model_khac_nhau_va_tinh_ca_gia_tren_nguong(self):
        bang = {"he_so_chung": {"he_so_ghi_cache_5m": 1.25, "he_so_ghi_cache_1h": 2.0, "he_so_batch": 0.5},
                "model": {"a": {"vao_usd": 1.0, "ra_usd": 2.0, "he_so_doc_cache": 0.1, "nguong_prompt_token": 10,
                                "vao_usd_tren_nguong": 5.0, "ra_usd_tren_nguong": 9.0},
                          "b": {"vao_usd": 3.0, "ra_usd": 4.0, "he_so_doc_cache": 0.5}}}
        with mock.patch("token_chung.gia.bang_gia", return_value=bang):
            dp = gia_du_phong()
        self.assertEqual((dp["vao_usd"], dp["ra_usd"]), (5.0, 9.0))           # từ giá trên ngưỡng của a
        self.assertAlmostEqual(dp["doc_cache_usd"], 1.5)                       # 3.0 x 0.5 của b, hơn 5.0 x 0.1 của a
        self.assertEqual(dp["nguon"]["vao_usd"], "a")
        self.assertEqual(dp["nguon"]["doc_cache_usd"], "b")
        self.assertAlmostEqual(dp["ghi_cache_5m_usd"], 6.25)
        self.assertAlmostEqual(dp["ghi_cache_1h_usd"], 10.0)


if __name__ == "__main__":
    unittest.main()
