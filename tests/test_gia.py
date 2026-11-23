"""Test tính tiền: chạy `python -m unittest -v tests.test_gia` ở thư mục gốc repo. Không gọi mạng."""
import unittest

from token_chung.gia import tinh_chi_phi


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


if __name__ == "__main__":
    unittest.main()
