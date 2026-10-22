import re
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

from balance_trees.showcase.build import ENGINE_META, build_site
from balance_trees.showcase.server import STATIC


class AssetReferences(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.engine = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta" and attrs.get("name") == "rotation-lab-engine":
            self.engine = attrs.get("content")
        for name in ("src", "href"):
            value = attrs.get(name, "")
            if value and not value.startswith(("#", "data:", "https:")):
                self.links.append(value)


class PagesBuildTests(unittest.TestCase):
    def test_staged_assets_resolve_under_a_github_project_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = build_site(Path(temporary) / "website")
            page = AssetReferences()
            page.feed((output / "index.html").read_text())
            self.assertEqual(page.engine, "browser")
            self.assertTrue((output / ".nojekyll").is_file())
            base = "https://example.github.io/experimental-balance-trees/"
            for reference in page.links:
                url = urlparse(urljoin(base, reference))
                self.assertTrue(url.path.startswith("/experimental-balance-trees/"))
                relative = url.path.removeprefix("/experimental-balance-trees/")
                self.assertTrue((output / relative).exists(), reference)
            for module in output.glob("*.mjs"):
                for reference in re.findall(
                    r"from\s+['\"]([^'\"]+)['\"]", module.read_text()
                ):
                    url = urlparse(urljoin(base + module.name, reference))
                    relative = url.path.removeprefix("/experimental-balance-trees/")
                    self.assertTrue((output / relative).is_file(), reference)

    def test_public_build_does_not_change_local_mode_or_copy_site_metadata(self):
        original = (STATIC / "index.html").read_bytes()
        with tempfile.TemporaryDirectory() as temporary:
            output = build_site(Path(temporary) / "website")
            self.assertNotIn(ENGINE_META, (output / "index.html").read_text())
            self.assertFalse((output / ".openai").exists())
            self.assertFalse((output / ".git").exists())
        self.assertEqual((STATIC / "index.html").read_bytes(), original)
        self.assertIn(ENGINE_META, original.decode())

    def test_existing_destination_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            marker = output / "keep.txt"
            marker.write_text("original")
            with self.assertRaises(FileExistsError):
                build_site(output)
            self.assertEqual(list(output.iterdir()), [marker])
            self.assertEqual(marker.read_text(), "original")

    def test_destination_cannot_overlap_the_website_source(self):
        for output in (STATIC, STATIC.parent, STATIC / "nested"):
            with self.subTest(output=output), self.assertRaises(ValueError):
                build_site(output)
