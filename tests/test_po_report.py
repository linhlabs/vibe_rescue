"""PO report renderer (RULES R13): two linked pages from Markdown, P codes, no emoji, fail closed."""

import re
import shutil
from pathlib import Path

import pytest

from scripts import po_report

FIX = Path(__file__).parent / "fixtures" / "po_report"


def _md():
    return ((FIX / "PO_SUMMARY.md").read_text(encoding="utf-8"),
            (FIX / "PO_DETAIL.md").read_text(encoding="utf-8"))


def _problems(summary, detail):
    with pytest.raises(po_report.ReportError) as e:
        po_report.build(summary, detail)
    return e.value.problems


def _metrics(cover):
    return re.findall(r"<div><b>([^<]+)</b>", cover.split('class="metrics"')[1])


def test_tokens_cover_the_markdown_subset():
    md = ("Mở đầu.\n\n**Hiện tại**\n\n- **Một** dòng\n  nối tiếp\n- Hai [P1]\n\n"
          "**Cần cải thiện trước nhất**\n\n1. Làm A\n\n| Mã | Ghi chú |\n|---|---|\n| P1 | `a|b` |\n\n"
          "> Ghi chú cuối.\n\n### 3.1 Tên (rủi ro cao)\n")
    toks = po_report.tokens(md)
    assert [t[0] for t in toks] == ["p", "label", "list", "label", "list", "table", "quote", "h3"]
    assert toks[1][1:] == ("now", "Hiện tại")
    assert toks[2][2] == ["**Một** dòng nối tiếp", "Hai [P1]"]
    assert toks[3][1] == "fix" and toks[4][1] is True
    assert toks[5][2] == [["P1", "`a|b`"]]
    assert po_report.groups(toks)[1][0][:3] == ("3.1", "Tên", "cao")


def test_header_properties_and_numbered_sections_are_read_from_markdown():
    problems = []
    doc = po_report.parse(_md()[0], "PO_SUMMARY.md", problems)
    assert problems == []
    assert doc.title == "Phân tích sổ hẹn khám mẫu"
    assert doc.prop("ngày") == "01/01/2026"
    assert doc.prop("Kết luận") == "Dùng nội bộ được. Chưa mở cho khách."
    assert list(doc.sections) == [str(i) for i in range(1, 9)]
    assert doc.intro.startswith("Dữ liệu giả")


def test_slides_follow_the_short_structure():
    res = po_report.build(*_md())
    s = res.summary_html
    # cover, 1, 2, features 7+2 rows, risk 4.1 alone + 4.2/4.3 paired, actions, 6+7, questions
    assert res.slides == 10 and s.count('<section class="slide') == 10
    assert 'data-slides="10"' in s
    cover = s.split('id="slide2"')[0]
    assert "Phân tích <em>sổ hẹn khám mẫu</em>" in cover
    assert "Dùng nội bộ được. Chưa mở cho khách." in cover
    assert _metrics(cover) == ["120", "3/9", "3", "4"]
    assert 'class="detail-link" href="PO_DETAIL.html"' in cover
    assert "Phần 3 · 1/2" in s and "Phần 3 · 2/2" in s
    assert s.count('<div class="pair">') == 1 and s.count('<div class="cols">') == 2
    assert '<span class="tag weak">Yếu</span>' in s and '<span class="tag high">Cao</span>' in s
    assert "10 / 10" in s
    assert "@media print" in s and "break-before:page" in s


def test_every_p_code_opens_its_appendix_row_and_pages_link_both_ways():
    res = po_report.build(*_md())
    rows = set(re.findall(r'<tr id="(P\d+)"', res.detail_html))
    assert rows == {f"P{i}" for i in range(1, 6)}
    from_slides = set(re.findall(r'href="PO_DETAIL\.html#(P\d+)"', res.summary_html))
    in_page = set(re.findall(r'href="#(P\d+)"', res.detail_html))
    assert from_slides and from_slides <= rows
    assert in_page and in_page <= rows
    assert 'href="PO_SUMMARY.html"' in res.detail_html
    assert res.codes == 5


def test_detail_page_is_a_notion_style_column():
    d = po_report.build(*_md()).detail_html
    assert "max-width:760px" in d
    assert re.search(r'<div class="k">Phiên bản</div><div class="v"><span class="tag gray">Bản chi tiết</span>', d)
    assert "<strong>Cách đọc</strong>" in d
    assert len(re.findall(r'<a href="#sec\d"><span>', d)) == 9
    assert '<div class="risk" id="s3.1">' in d and '<div class="risk" id="s4.2">' in d
    assert '<span class="tag med">Rủi ro trung bình</span>' in d
    assert '<details class="appendix">' in d and "<details class=\"appendix\" open" not in d
    assert "<code>ma|ngay</code>" in d
    assert d.count('class="callout') >= 3  # how to read, verdict, the closing note


def test_output_has_no_emoji_and_needs_no_network():
    res = po_report.build(*_md())
    for page in (res.summary_html, res.detail_html):
        assert not po_report.EMOJI_RE.search(page)
        assert "<svg" in page
        assert not re.search(r'(?:src|href)="(?:https?:)?//', page)
        assert "<link" not in page and "@import" not in page and "url(" not in page


def test_emoji_in_markdown_fails_closed():
    summary, detail = _md()
    problems = _problems(summary.replace("Tin nhắn nhắc lịch gửi trùng", "Tin nhắn \U0001F4E9 gửi trùng"), detail)
    assert any("PO_SUMMARY.md:" in p and "emoji" in p for p in problems)


def test_p_code_without_appendix_row_fails_closed():
    summary, detail = _md()
    problems = _problems(summary.replace("[P3]", "[P99]"), detail)
    assert any("P99" in p and "phụ lục" in p for p in problems)


def test_slide_limits_and_missing_sections_fail_closed():
    summary, detail = _md()
    extra = summary.replace("| 4 | Quyết có mở", "| 5 | A | Nhỏ | Dev |\n| 6 | B | Nhỏ | Dev |\n| 7 | C | Nhỏ | Dev |\n| 4 | Quyết có mở")
    assert any("7 việc, tối đa 6" in p for p in _problems(extra, detail))
    no_section = re.sub(r"## 7\. Lần này chưa kiểm.*?---\n", "", summary, flags=re.DOTALL)
    assert any("thiếu mục '## 7." in p for p in _problems(no_section, detail))
    no_verdict = summary.replace("- **Kết luận:** Dùng nội bộ được. Chưa mở cho khách.\n", "")
    assert any("Kết luận" in p for p in _problems(no_verdict, detail))


def test_cover_numbers_fall_back_to_counts_from_the_content():
    summary, detail = _md()
    summary = re.sub(r"- \*\*Số chính:\*\*.*\n", "", summary)
    cover = po_report.build(summary, detail).summary_html.split('id="slide2"')[0]
    assert _metrics(cover) == ["3/9", "3", "4", "5"]


def test_markdown_text_is_escaped_and_unsafe_links_dropped():
    summary, detail = _md()
    summary = summary.replace("- **Đang ổn:** đăng ký", "- <script>alert(1)</script> [bấm](javascript:alert(1)) đăng ký")
    s = po_report.build(summary, detail).summary_html
    assert "<script>alert(1)" not in s and "&lt;script&gt;alert(1)" in s
    assert "javascript:" not in s


def test_cli_writes_both_pages_or_nothing(tmp_path, capsys):
    review = tmp_path / "review"
    shutil.copytree(FIX, review)
    assert po_report.main([str(review)]) == 0
    assert (review / "PO_SUMMARY.html").is_file() and (review / "PO_DETAIL.html").is_file()
    assert "slides=10" in capsys.readouterr().out

    broken = tmp_path / "broken"
    shutil.copytree(FIX, broken)
    (broken / "PO_DETAIL.md").write_text(_md()[1].replace("| P5 |", "| X5 |"), encoding="utf-8")
    assert po_report.main(["--summary", str(broken / "PO_SUMMARY.md"), "--detail", str(broken / "PO_DETAIL.md")]) == 2
    assert "P5" in capsys.readouterr().err
    assert not list(broken.glob("*.html"))

    assert po_report.main([str(tmp_path / "missing")]) == 2
