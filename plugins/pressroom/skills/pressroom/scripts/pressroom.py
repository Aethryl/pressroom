import argparse
import base64
import contextlib
import glob
import json
import os
import platform
import re
import select
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

PAGE_SIZES = {"A4": "210mm 297mm", "Letter": "8.5in 11in", "A5": "148mm 210mm"}

SETTLE_JS = """(async () => {
  await document.fonts.ready;
  await Promise.all([...document.images].map(i => i.complete ? 0 : new Promise(r => { i.onload = i.onerror = r; })));
  await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
  return {
    fonts: [...document.fonts].filter(f => f.status === 'error').map(f => f.family),
    images: [...document.images].filter(i => !i.naturalWidth).map(i => i.currentSrc || i.src),
  };
})()"""

FOOTER_TEMPLATE = (
    '<div style="width:100%;font:8px sans-serif;color:#666;text-align:center;">'
    '<span class="pageNumber"></span> / <span class="totalPages"></span></div>'
)


REFERENCES = Path(__file__).resolve().parent.parent / "references"
FONT_TYPES = {".woff2": "font/woff2", ".woff": "font/woff", ".ttf": "font/ttf", ".otf": "font/otf"}
FONT_URL = re.compile(r"url\(\s*(['\"]?)([^'\")]+?\.(?:woff2|woff|ttf|otf))\1\s*\)")


class PressError(Exception):
    pass


def template_names() -> list[str]:
    return sorted(p.stem for p in (REFERENCES / "templates").glob("*.html"))


def inline_fonts(css: str, base_dir: Path) -> str:
    def embed(match: re.Match) -> str:
        ref = match.group(2)
        if ref.startswith(("data:", "http:", "https:")):
            return match.group(0)
        path = (base_dir / ref).resolve()
        if not path.is_file():
            raise PressError(f"font file not found: {path}")
        data = base64.b64encode(path.read_bytes()).decode()
        return f'url("data:{FONT_TYPES[path.suffix.lower()]};base64,{data}")'

    return FONT_URL.sub(embed, css)


def assemble(template: str, theme_css: str = "", theme_dir: Path | None = None) -> str:
    path = REFERENCES / "templates" / f"{template}.html"
    if not path.is_file():
        raise PressError(f"unknown template {template!r}; choose from: {', '.join(template_names())}")
    base = inline_fonts((REFERENCES / "base.css").read_text(), REFERENCES)
    html = path.read_text()
    html = html.replace('<style data-pr="base"></style>', f'<style data-pr="base">\n{base}</style>')
    if theme_css:
        theme_css = inline_fonts(theme_css, theme_dir or Path.cwd())
        return html.replace('<style data-pr="theme"></style>', f'<style data-pr="theme">\n{theme_css}</style>')
    return html.replace('<style data-pr="theme"></style>\n', "")


def chrome_candidates() -> list[str]:
    found = []
    env = os.environ.get("PRESSROOM_CHROME")
    if env:
        found.append(env)
    cache = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", Path.home() / ".cache" / "ms-playwright"))
    if platform.system() == "Darwin":
        cache = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", Path.home() / "Library" / "Caches" / "ms-playwright"))
    patterns = [
        "chromium-*/chrome-linux*/chrome",
        "chromium_headless_shell-*/chrome-headless-shell-linux*/chrome-headless-shell",
        "chromium-*/chrome-mac*/Chromium.app/Contents/MacOS/Chromium",
        "chromium-*/chrome-mac*/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
        "chromium_headless_shell-*/chrome-headless-shell-mac*/chrome-headless-shell",
    ]
    for pattern in patterns:
        found.extend(sorted(glob.glob(str(cache / pattern)), reverse=True))
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "chrome", "microsoft-edge"):
        path = shutil.which(name)
        if path:
            found.append(path)
    found.extend(
        [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ]
    )
    return found


def find_chrome() -> str:
    for path in chrome_candidates():
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    raise PressError(
        "no Chromium found. Install one (`npx playwright install chromium`, or the distro chromium package) "
        "or point PRESSROOM_CHROME at a Chrome/Chromium binary."
    )


class Browser:
    def __init__(self, timeout: float = 60.0):
        self.timeout = timeout
        self.profile = tempfile.mkdtemp(prefix="pressroom-")
        cmd_read, self.cmd_write = os.pipe()
        self.out_read, out_write = os.pipe()
        args = [
            find_chrome(),
            "--headless",
            "--remote-debugging-pipe",
            f"--user-data-dir={self.profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            "--disable-gpu",
            "--hide-scrollbars",
            "--mute-audio",
            "--font-render-hinting=none",
        ]
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            args.append("--no-sandbox")
        os.set_inheritable(cmd_read, True)
        os.set_inheritable(out_write, True)

        def wire_fds() -> None:
            os.dup2(cmd_read, 3)
            os.dup2(out_write, 4)

        self.proc = subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=False,
            preexec_fn=wire_fds,
        )
        os.close(cmd_read)
        os.close(out_write)
        self.buffer = b""
        self.events: list[dict] = []
        self.next_id = 0

    def __enter__(self) -> "Browser":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self.send("Browser.close")
        with contextlib.suppress(OSError):
            os.close(self.cmd_write)
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        with contextlib.suppress(OSError):
            os.close(self.out_read)
        shutil.rmtree(self.profile, ignore_errors=True)

    def _read_message(self, deadline: float) -> dict:
        while b"\0" not in self.buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise PressError("timed out waiting for Chromium")
            ready, _, _ = select.select([self.out_read], [], [], remaining)
            if not ready:
                continue
            chunk = os.read(self.out_read, 1 << 20)
            if not chunk:
                raise PressError("Chromium exited unexpectedly")
            self.buffer += chunk
        raw, self.buffer = self.buffer.split(b"\0", 1)
        return json.loads(raw)

    def send(self, method: str, params: dict | None = None, session: str | None = None) -> dict:
        self.next_id += 1
        message: dict = {"id": self.next_id, "method": method, "params": params or {}}
        if session:
            message["sessionId"] = session
        os.write(self.cmd_write, json.dumps(message).encode() + b"\0")
        deadline = time.monotonic() + self.timeout
        while True:
            reply = self._read_message(deadline)
            if reply.get("id") == self.next_id:
                if "error" in reply:
                    raise PressError(f"{method}: {reply['error'].get('message')}")
                return reply.get("result", {})
            if "method" in reply:
                self.events.append(reply)

    def wait_event(self, predicate, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while True:
            for event in self.events:
                if predicate(event):
                    self.events.remove(event)
                    return True
            if time.monotonic() >= deadline:
                return False
            try:
                event = self._read_message(deadline)
            except PressError:
                return False
            if "method" in event:
                self.events.append(event)

    def open(self, url: str, width: int = 1240, height: int = 1754) -> str:
        target = self.send("Target.createTarget", {"url": "about:blank"})["targetId"]
        session = self.send("Target.attachToTarget", {"targetId": target, "flatten": True})["sessionId"]
        self.send("Page.enable", session=session)
        self.send("Page.setLifecycleEventsEnabled", {"enabled": True}, session=session)
        self.send(
            "Emulation.setDeviceMetricsOverride",
            {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False},
            session=session,
        )
        self.send("Page.navigate", {"url": url}, session=session)
        loaded = self.wait_event(
            lambda e: e.get("sessionId") == session and e.get("method") == "Page.loadEventFired", self.timeout
        )
        if not loaded:
            raise PressError(f"page did not finish loading within {self.timeout:.0f}s: {url}")
        self.wait_event(
            lambda e: (
                e.get("sessionId") == session
                and e.get("method") == "Page.lifecycleEvent"
                and e["params"].get("name") == "networkIdle"
            ),
            min(self.timeout, 15),
        )
        return session

    def settle(self, session: str) -> dict:
        result = self.send(
            "Runtime.evaluate",
            {"expression": SETTLE_JS, "awaitPromise": True, "returnByValue": True},
            session=session,
        )
        return result.get("result", {}).get("value") or {}

    def evaluate(self, session: str, expression: str) -> None:
        self.send("Runtime.evaluate", {"expression": expression, "awaitPromise": True}, session=session)


@dataclass
class RenderResult:
    pdf: Path
    pages: int | None
    warnings: list[str]


def page_size_css(fmt: str | None, landscape: bool) -> str | None:
    if not fmt and not landscape:
        return None
    size = PAGE_SIZES[fmt or "A4"]
    if landscape:
        w, h = size.split()
        size = f"{h} {w}"
    return f"@page {{ size: {size}; }}"


def render_pdf(
    html: Path,
    out: Path,
    fmt: str | None = None,
    landscape: bool = False,
    footer_numbers: bool = False,
    timeout: float = 60.0,
) -> RenderResult:
    if not html.is_file():
        raise PressError(f"no such file: {html}")
    warnings: list[str] = []
    with Browser(timeout=timeout) as browser:
        session = browser.open(html.resolve().as_uri())
        override = page_size_css(fmt, landscape)
        if override:
            browser.evaluate(
                session,
                "(() => { const s = document.createElement('style'); s.textContent = "
                + json.dumps(override)
                + "; document.head.appendChild(s); })()",
            )
        state = browser.settle(session)
        warnings += [f"font failed to load: {f}" for f in state.get("fonts", [])]
        warnings += [f"image failed to load: {i}" for i in state.get("images", [])]
        params: dict = {
            "printBackground": True,
            "preferCSSPageSize": True,
            "displayHeaderFooter": footer_numbers,
            "generateDocumentOutline": True,
            "generateTaggedPDF": True,
        }
        if footer_numbers:
            params["headerTemplate"] = "<span></span>"
            params["footerTemplate"] = FOOTER_TEMPLATE
        data = browser.send("Page.printToPDF", params, session=session)["data"]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(base64.b64decode(data))
    return RenderResult(out, pdf_page_count(out), warnings)


def pdf_page_count(pdf: Path) -> int | None:
    if not shutil.which("pdfinfo"):
        return None
    info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True)
    for line in info.stdout.splitlines():
        if line.startswith("Pages:"):
            return int(line.split()[1])
    return None


def require_poppler() -> None:
    if not shutil.which("pdftoppm"):
        raise PressError(
            "pdftoppm not found; install poppler (Fedora: poppler-utils, Debian/Ubuntu: poppler-utils, macOS: brew install poppler)"
        )


def rasterize(pdf: Path, outdir: Path, dpi: int, first: int | None = None, last: int | None = None) -> list[Path]:
    require_poppler()
    if not pdf.is_file():
        raise PressError(f"no such file: {pdf}")
    cmd = ["pdftoppm", "-png", "-r", str(dpi)]
    if first:
        cmd += ["-f", str(first)]
    if last:
        cmd += ["-l", str(last)]
    subprocess.run([*cmd, str(pdf), str(outdir / "p")], check=True)
    return sorted(outdir.glob("p-*.png"))


def sheet_html(pages: list[Path], columns: int) -> str:
    cells = "".join(
        f'<figure><img src="{p.resolve().as_uri()}"><figcaption>{i}</figcaption></figure>'
        for i, p in enumerate(pages, 1)
    )
    return (
        "<!doctype html><meta charset=utf-8><style>"
        "html,body{margin:0;background:#8a8f98}"
        f"main{{display:grid;grid-template-columns:repeat({columns},1fr);gap:24px;padding:24px;width:max-content}}"
        "figure{margin:0;display:grid;gap:6px;justify-items:center}"
        "img{display:block;width:360px;background:#fff;box-shadow:0 2px 8px #0006}"
        "figcaption{font:600 14px sans-serif;color:#fff}"
        f"</style><main>{cells}</main>"
    )


def make_sheet(pdf: Path, out: Path, columns: int = 4, dpi: int = 60, timeout: float = 60.0) -> int:
    with tempfile.TemporaryDirectory(prefix="pressroom-sheet-") as tmp:
        pages = rasterize(pdf, Path(tmp), dpi)
        if not pages:
            raise PressError(f"no pages rendered from {pdf}")
        columns = max(1, min(columns, len(pages)))
        index = Path(tmp) / "sheet.html"
        index.write_text(sheet_html(pages, columns))
        with Browser(timeout=timeout) as browser:
            session = browser.open(index.as_uri(), width=400, height=400)
            browser.settle(session)
            box = browser.send(
                "Runtime.evaluate",
                {
                    "expression": "(() => { const r = document.querySelector('main').getBoundingClientRect();"
                    " return [Math.ceil(r.width), Math.ceil(r.height)]; })()",
                    "returnByValue": True,
                },
                session=session,
            )["result"]["value"]
            shot = browser.send(
                "Page.captureScreenshot",
                {
                    "format": "png",
                    "captureBeyondViewport": True,
                    "clip": {"x": 0, "y": 0, "width": box[0], "height": box[1], "scale": 1},
                },
                session=session,
            )["data"]
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(base64.b64decode(shot))
        return len(pages)


def make_page_image(pdf: Path, page: int, out: Path, dpi: int = 110) -> None:
    with tempfile.TemporaryDirectory(prefix="pressroom-page-") as tmp:
        pages = rasterize(pdf, Path(tmp), dpi, page, page)
        if not pages:
            raise PressError(f"page {page} not found in {pdf}")
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(pages[0], out)


def parse_pgm(data: bytes) -> tuple[int, int, bytes]:
    fields: list[bytes] = []
    pos = 0
    while len(fields) < 4:
        while data[pos : pos + 1].isspace():
            pos += 1
        if data[pos : pos + 1] == b"#":
            pos = data.index(b"\n", pos) + 1
            continue
        end = pos
        while not data[end : end + 1].isspace():
            end += 1
        fields.append(data[pos:end])
        pos = end
    if fields[0] != b"P5":
        raise PressError("unexpected raster format from pdftoppm")
    width, height, maxval = int(fields[1]), int(fields[2]), int(fields[3])
    if maxval > 255:
        raise PressError("16-bit raster not supported")
    pixels = data[pos + 1 : pos + 1 + width * height]
    return width, height, pixels


@dataclass
class PageStats:
    number: int
    ink: float
    content_bottom: float


def page_stats(number: int, width: int, height: int, pixels: bytes, footer_band: float = 0.06) -> PageStats:
    body_rows = int(height * (1 - footer_band))
    inked = 0
    bottom = 0
    for y in range(body_rows):
        row = pixels[y * width : (y + 1) * width]
        dark = sum(1 for v in row if v < 235)
        if dark:
            inked += dark
            bottom = y + 1
    return PageStats(number, inked / (width * body_rows), bottom / height)


def check_pdf(pdf: Path, dpi: int = 24) -> list[PageStats]:
    require_poppler()
    if not pdf.is_file():
        raise PressError(f"no such file: {pdf}")
    with tempfile.TemporaryDirectory(prefix="pressroom-check-") as tmp:
        subprocess.run(["pdftoppm", "-gray", "-r", str(dpi), str(pdf), str(Path(tmp) / "p")], check=True)
        stats = []
        for i, path in enumerate(sorted(Path(tmp).glob("p-*.pgm")), 1):
            stats.append(page_stats(i, *parse_pgm(path.read_bytes())))
        return stats


def page_issues(stats: list[PageStats]) -> list[str]:
    issues = []
    for s in stats:
        last = s.number == len(stats)
        if s.ink < 0.002:
            issues.append(f"page {s.number}: blank")
        elif not last and s.content_bottom < 0.55:
            issues.append(f"page {s.number}: content ends at {s.content_bottom:.0%} of the page (gap before a break)")
    return issues


def default_out(src: Path, suffix: str) -> Path:
    return src.with_suffix(suffix)


def cmd_new(args: argparse.Namespace) -> int:
    if args.list or not args.template:
        print("\n".join(template_names()))
        return 0
    if not args.output:
        raise PressError("give an output path: new <template> <out.html>")
    out = Path(args.output)
    if out.exists() and not args.force:
        raise PressError(f"{out} exists; pass --force to overwrite")
    theme = ""
    theme_dir = None
    if args.theme:
        theme_path = Path(args.theme)
        if not theme_path.is_file():
            raise PressError(f"no such theme file: {theme_path}")
        theme = theme_path.read_text()
        theme_dir = theme_path.resolve().parent
    html = assemble(args.template, theme, theme_dir)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    print(out.resolve())
    return 0


def cmd_pdf(args: argparse.Namespace) -> int:
    html = Path(args.html)
    out = Path(args.output) if args.output else default_out(html, ".pdf")
    result = render_pdf(html, out, args.format, args.landscape, args.footer_numbers, args.timeout)
    for warning in result.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    pages = f" ({result.pages} pages)" if result.pages else ""
    print(f"{result.pdf.resolve()}{pages}")
    return 0


def cmd_sheet(args: argparse.Namespace) -> int:
    pdf = Path(args.pdf)
    out = Path(args.output) if args.output else pdf.with_name(pdf.stem + "-sheet.png")
    count = make_sheet(pdf, out, args.columns, args.dpi, args.timeout)
    print(f"{out.resolve()} ({count} pages)")
    return 0


def cmd_page(args: argparse.Namespace) -> int:
    pdf = Path(args.pdf)
    out = Path(args.output) if args.output else pdf.with_name(f"{pdf.stem}-p{args.number}.png")
    make_page_image(pdf, args.number, out, args.dpi)
    print(out.resolve())
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    stats = check_pdf(Path(args.pdf))
    print(f"{len(stats)} pages")
    for s in stats:
        print(f"  page {s.number}: ink {s.ink:.1%}, content to {s.content_bottom:.0%} of height")
    issues = page_issues(stats)
    for issue in issues:
        print(f"issue: {issue}")
    if not issues:
        print("no blank or underfilled pages")
    return 1 if issues else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pressroom.py", description="Render print-ready HTML documents to PDF.")
    parser.add_argument("--timeout", type=float, default=60.0, help="seconds to wait for Chromium (default 60)")
    sub = parser.add_subparsers(dest="command", required=True)

    new = sub.add_parser("new", help="start a self-contained HTML document from a template")
    new.add_argument("template", nargs="?", help="template name; omit or pass --list to list them")
    new.add_argument("output", nargs="?", help="where to write the HTML")
    new.add_argument(
        "--theme",
        help="CSS file with token overrides, fonts and logo, inlined after the base styles; font files it references by relative path are embedded",
    )
    new.add_argument("--list", action="store_true", help="list templates")
    new.add_argument("--force", action="store_true", help="overwrite an existing file")
    new.set_defaults(func=cmd_new)

    pdf = sub.add_parser("pdf", help="render an HTML file to PDF with headless Chromium")
    pdf.add_argument("html")
    pdf.add_argument("-o", "--output", help="output PDF (default: next to the HTML)")
    pdf.add_argument("--format", choices=sorted(PAGE_SIZES), help="override the CSS @page size")
    pdf.add_argument("--landscape", action="store_true", help="override the CSS @page orientation")
    pdf.add_argument(
        "--footer-numbers",
        action="store_true",
        help="add 'n / total' via Chromium's footer template instead of CSS @page margin boxes",
    )
    pdf.set_defaults(func=cmd_pdf)

    sheet = sub.add_parser("sheet", help="contact sheet PNG of every page, for visual review")
    sheet.add_argument("pdf")
    sheet.add_argument("-o", "--output", help="output PNG (default: <pdf>-sheet.png)")
    sheet.add_argument("--columns", type=int, default=4)
    sheet.add_argument("--dpi", type=int, default=60)
    sheet.set_defaults(func=cmd_sheet)

    page = sub.add_parser("page", help="hi-res PNG of one page")
    page.add_argument("pdf")
    page.add_argument("number", type=int)
    page.add_argument("-o", "--output", help="output PNG (default: <pdf>-p<n>.png)")
    page.add_argument("--dpi", type=int, default=110)
    page.set_defaults(func=cmd_page)

    check = sub.add_parser("check", help="page count and blank or underfilled pages; exit 1 on issues")
    check.add_argument("pdf")
    check.set_defaults(func=cmd_check)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except PressError as error:
        print(f"pressroom: {error}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as error:
        print(f"pressroom: {error.cmd[0]} failed with exit code {error.returncode}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
