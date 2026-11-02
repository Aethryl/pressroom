import shutil
from pathlib import Path

import pressroom as pr
import pytest


def has_renderer() -> bool:
    try:
        pr.find_chrome()
    except pr.PressError:
        return False
    return bool(shutil.which("pdftoppm") and shutil.which("pdfinfo"))


needs_renderer = pytest.mark.skipif(not has_renderer(), reason="needs Chromium and poppler")


def pgm(width: int, height: int, dark_rows: range) -> bytes:
    pixels = bytearray(b"\xff" * width * height)
    for y in dark_rows:
        pixels[y * width : (y + 1) * width] = b"\x00" * width
    return f"P5\n# made by test\n{width} {height}\n255\n".encode() + bytes(pixels)


def test_parse_pgm_skips_comments():
    width, height, pixels = pr.parse_pgm(pgm(4, 3, range(1, 2)))
    assert (width, height) == (4, 3)
    assert pixels[4:8] == b"\x00" * 4


def test_page_stats_ignores_footer_band():
    stats = pr.page_stats(1, *pr.parse_pgm(pgm(10, 100, range(97, 99))))
    assert stats.ink == 0


def test_page_issues_flags_blank_and_short_pages():
    stats = [
        pr.PageStats(1, 0.10, 0.30),
        pr.PageStats(2, 0.0, 0.0),
        pr.PageStats(3, 0.10, 0.90),
        pr.PageStats(4, 0.01, 0.10),
    ]
    assert pr.page_issues(stats) == [
        "page 1: content ends at 30% of the page (gap before a break)",
        "page 2: blank",
    ]


def test_page_size_override():
    assert pr.page_size_css(None, False) is None
    assert pr.page_size_css("Letter", False) == "@page { size: 8.5in 11in; }"
    assert pr.page_size_css(None, True) == "@page { size: 297mm 210mm; }"


def test_every_template_assembles_with_base_and_theme():
    names = pr.template_names()
    assert {"report", "letter-nl", "letter", "quote", "one-pager", "cv", "cover-letter"} <= set(names)
    for name in names:
        html = pr.assemble(name, ":root { --pr-accent: red; }")
        assert "--pr-paper" in html
        assert "--pr-accent: red" in html
        assert 'data-pr="base"></style>' not in html
        plain = pr.assemble(name)
        assert 'data-pr="theme"' not in plain


def test_fonts_are_embedded():
    html = pr.assemble("report")
    assert "data:font/woff2;base64," in html
    assert 'url("fonts/' not in html
    assert "fonts.googleapis.com" not in html


def test_theme_fonts_resolve_next_to_theme(tmp_path: Path):
    (tmp_path / "fonts").mkdir()
    (tmp_path / "fonts" / "brand.ttf").write_bytes(b"font")
    theme = '@font-face { font-family: Brand; src: url("fonts/brand.ttf"); }'
    assert 'url("data:font/ttf;base64,Zm9udA==")' in pr.assemble("letter", theme, tmp_path)
    with pytest.raises(pr.PressError, match="font file not found"):
        pr.assemble("letter", 'src: url("missing.woff2")', tmp_path)


def test_unknown_template_lists_choices():
    with pytest.raises(pr.PressError, match="choose from"):
        pr.assemble("brochure")


def test_find_chrome_reports_missing_browser(monkeypatch):
    monkeypatch.setattr(pr, "chrome_candidates", lambda: ["/nonexistent/chrome"])
    with pytest.raises(pr.PressError, match="PRESSROOM_CHROME"):
        pr.find_chrome()


def test_new_refuses_to_overwrite(tmp_path: Path):
    out = tmp_path / "doc.html"
    out.write_text("mine")
    assert pr.main(["new", "report", str(out)]) == 2
    assert out.read_text() == "mine"


@needs_renderer
def test_render_check_and_sheet(tmp_path: Path):
    html = tmp_path / "doc.html"
    html.write_text(
        "<!doctype html><style>@page { size: A4; margin: 15mm; } .fill { height: 200mm; background: #c00; }"
        "</style><div class=fill></div><div class=fill></div>"
    )
    result = pr.render_pdf(html, tmp_path / "doc.pdf")
    assert result.pages == 2
    stats = pr.check_pdf(result.pdf)
    assert len(stats) == 2
    assert stats[0].ink > 0.3
    sheet = tmp_path / "sheet.png"
    assert pr.make_sheet(result.pdf, sheet) == 2
    assert sheet.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
