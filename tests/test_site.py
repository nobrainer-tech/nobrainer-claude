from html.parser import HTMLParser
from pathlib import Path
import struct
import unittest
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.references = []
        self.meta = {}
        self.canonical = None
        self.copy_buttons = 0

    def handle_starttag(self, tag, attributes):
        values = dict(attributes)
        if "id" in values:
            self.ids.append(values["id"])
        for key in ("href", "src"):
            if values.get(key):
                self.references.append(values[key])
        if tag == "meta":
            self.meta.setdefault(values.get("property") or values.get("name"), values.get("content"))
        if tag == "link" and values.get("rel") == "canonical":
            self.canonical = values.get("href")
        if tag == "button" and "data-copy-prompt" in values:
            self.copy_buttons += 1


class SiteTests(unittest.TestCase):
    def test_shared_brand_typography_is_loaded_last(self):
        text = (ROOT / "site/index.html").read_text(encoding="utf-8")
        css = (ROOT / "site/assets/brand-typography.css").read_text(encoding="utf-8")
        self.assertIn('href="assets/brand-typography.css?v=20260927-flow-header"', text)
        self.assertGreater(text.index("assets/brand-typography.css"), text.rfind("</style>"))
        self.assertIn("font-family: var(--font-brand)", css)
        self.assertIn("font-weight: 700", css)
        self.assertIn("clamp(54px, 6.15vw, 88px)", css)
        self.assertIn("header .brand .brand-flow", css)
        self.assertIn("font-weight: 750", css)
        self.assertIn('class="brand" href="#top"', text)
        self.assertIn('<body id="top">', text)
        self.assertIn('class="brand-dot"', text)
        self.assertIn('<nav class="breadcrumbs" aria-label="Breadcrumb">', text)
        self.assertIn('href="https://nobrainer.tech/">nobrainer.tech</a>', text)
        self.assertIn('aria-current="page">NoBrainer Claude</li>', text)
        self.assertIn("@media (max-width: 360px)", css)

    def test_local_links_and_anchor_targets_resolve(self):
        parser = Page()
        parser.feed((SITE / "index.html").read_text(encoding="utf-8"))
        self.assertEqual(len(parser.ids), len(set(parser.ids)))
        for reference in parser.references:
            parts = urlsplit(reference)
            if parts.scheme or parts.netloc:
                continue
            if parts.path:
                target = (SITE / parts.path).resolve()
                self.assertTrue(target.is_relative_to(SITE.resolve()))
                self.assertTrue(target.is_file(), reference)
            elif parts.fragment:
                self.assertIn(parts.fragment, parser.ids)
        self.assertEqual(parser.canonical, "https://nobrainer.tech/claude/")
        self.assertIn("https://github.com/nobrainer-tech/nobrainer-claude", parser.references)
        self.assertIn("https://github.com/nobrainer-tech/nobrainer-tech-flow", parser.references)
        self.assertGreaterEqual(parser.copy_buttons, 1)
        self.assertIn("install-prompt", parser.ids)
        self.assertIn("copy-status", parser.ids)

    def test_social_image_matches_metadata(self):
        parser = Page()
        parser.feed((SITE / "index.html").read_text(encoding="utf-8"))
        self.assertEqual(parser.meta["og:image"], "https://nobrainer.tech/claude/assets/social-card.png")
        payload = (SITE / "assets/social-card.png").read_bytes()
        self.assertEqual(payload[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", payload[16:24]), (1200, 630))

    def test_publish_tree_contains_only_public_assets(self):
        allowed = {".html", ".css", ".js", ".svg", ".png", ".webp", ".ico", ".xml", ".txt"}
        for path in SITE.rglob("*"):
            self.assertFalse(any(part.startswith(".") for part in path.relative_to(SITE).parts), str(path))
            if path.is_file():
                self.assertIn(path.suffix, allowed)


if __name__ == "__main__":
    unittest.main()
