import unittest

from bs4 import BeautifulSoup

from src.components.shared.layout.app_shell import app_shell
from src.pages import gallery, generation, home, profile


class SharedLayoutTests(unittest.TestCase):
    def test_pages_have_one_shell_and_the_correct_active_link(self):
        for module, path in (
            (home, "/"),
            (generation, "/generation"),
            (gallery, "/gallery"),
            (profile, "/profile"),
        ):
            with self.subTest(path=path):
                soup = BeautifulSoup(str(module.page()), "html.parser")
                self.assertEqual(len(soup.select(".site-sidebar")), 1)
                self.assertEqual(len(soup.select(".site-header")), 1)
                self.assertEqual(len(soup.select(".site-footer")), 1)
                current = soup.select('.site-sidebar [aria-current="page"]')
                self.assertEqual(len(current), 1)
                self.assertEqual(current[0]["href"], path)
                self.assertEqual(len(soup.select("main#main-content")), 1)
                self.assertEqual(
                    soup.select_one(".site-skip-link")["href"], "#main-content"
                )
                self.assertEqual(soup.select_one(".site-skip-link")["pp-spa"], "false")

    def test_title_is_text_but_page_content_is_html(self):
        title = '<script>alert("title")</script> & profile'
        soup = BeautifulSoup(
            str(app_shell('<p id="content">Content</p>', title=title)), "html.parser"
        )
        self.assertEqual(soup.select_one(".site-header__title").get_text(), title)
        self.assertIsNone(soup.find("script"))
        self.assertEqual(soup.select_one("main #content").get_text(), "Content")

    def test_unknown_active_page_cannot_inject_markup(self):
        soup = BeautifulSoup(
            str(app_shell("", active_page='"><script>bad()</script>')), "html.parser"
        )
        self.assertIsNone(soup.find("script"))
        self.assertEqual(soup.select("[aria-current]"), [])

    def test_existing_call_without_active_page_still_renders(self):
        soup = BeautifulSoup(str(app_shell("Content")), "html.parser")
        self.assertIn("Content", soup.select_one("main").get_text())
        paths = {link["href"] for link in soup.select(".site-sidebar a")}
        self.assertEqual(paths, {"/", "/generation", "/gallery", "/profile"})


if __name__ == "__main__":
    unittest.main()
