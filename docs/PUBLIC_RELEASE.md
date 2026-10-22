# PUBLIC RELEASE — phát hành source sạch

Lịch sử Git hiện tại từng chứa report nội bộ. Xóa report ở HEAD **không xóa chúng
khỏi Git objects**. Không push nhánh/lịch sử hiện tại lên remote public.

## Tạo bản ứng viên không mang lịch sử

```bash
python3 scripts/public_snapshot.py --out reports/public-release/vibe-rescue-source.tar.gz
mkdir -p /tmp/vibe-rescue-review
tar -xzf reports/public-release/vibe-rescue-source.tar.gz -C /tmp/vibe-rescue-review
```

Snapshot chỉ lấy file trong Git index và file mới chưa ignore ở working tree,
loại `reports/`, `.rescue/`, binary/cache và log phiên. Script từ chối symlink;
archive có `SNAPSHOT_MANIFEST.json` ở ngoài thư mục source với SHA-256 từng file,
không có `.git`.
**Snapshot không tự chứng minh source không chứa bí mật**. Kiểm nội dung, license,
đường dẫn nội bộ và credential bằng mắt lẫn secret scanner trước khi công khai.

## Cổng phát hành

0. Đọc `docs/REPO_RUNTIME_ATLAS.md` và đóng các blocker R1–R4 bằng test phản
   chứng trước khi quảng bá auto-repair an toàn. Chạy
   `python3 scripts/repo_explorer.py --check` để sơ đồ khớp working tree.
1. Trong bản giải nén, tạo Git repo mới chỉ sau khi đã duyệt toàn bộ file.
   Chạy `python3 -m pytest -q` và `uvx --from ruff==0.16.5 ruff check .`.
2. Chạy atlas trên fixture Python/JS/TS/Rust/Go/Java/PHP/C# và xác nhận HTML/SVG,
   PDF nếu đã cài renderer. `partial`, `unmapped`, `unavailable` hoặc `unknown`
   phải được giải thích; không ghi “full logic chính xác” từ static graph.
3. Rà `SNAPSHOT_MANIFEST.json`, file license và output scanner. Ghi SHA-256 của
   tarball và kết quả kiểm vào release record. Với Gitleaks `dir` trên bản giải
   nén, **đọc dòng số byte đã quét**: 0 byte là lỗi coverage, không phải 0 leak.
   `.gitleaks.toml` từng có regex `.rescue/` khớp `vibe_rescue/` và bỏ qua cả
   source; regression test `tests/test_gitleaks_config.py` bảo vệ case này.
4. Chỉ tạo remote public mới từ source đã duyệt, với **lịch sử Git mới**. Kiểm
   cả commits/tags và scan lại sau khi tạo commit đầu; không thêm remote cũ.

Public release là quyết định của owner. Harness không tự push hoặc publish.
