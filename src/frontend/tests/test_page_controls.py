import unittest

from bs4 import BeautifulSoup

from src.pages import gallery, generation, home


class PageControlsTests(unittest.TestCase):
    def test_home_keeps_navigation_and_dialog_controls_available(self):
        soup = BeautifulSoup(str(home.page()), "html.parser")
        self.assertEqual(soup.select_one(".generate-button")["href"], "/generation")
        for selector in ("#avatarButton", "#closeModal", ".modal-backdrop"):
            with self.subTest(selector=selector):
                button = soup.select_one(selector)
                self.assertFalse(button.has_attr("disabled"))
                self.assertTrue(button.get("onclick"))
        self.assertEqual(len(soup.select(".ui-image-placeholder")), 5)

    def test_auth_does_not_offer_an_unimplemented_submission(self):
        soup = BeautifulSoup(str(home.page()), "html.parser")
        submit = soup.select_one('#loginForm button[type="submit"]')
        self.assertTrue(submit.has_attr("disabled"))
        self.assertTrue(submit.get("title"))
        switch = soup.select_one("#switchToRegister")
        self.assertEqual(switch.name, "button")
        self.assertEqual(switch["type"], "button")
        self.assertTrue(switch.has_attr("disabled"))

    def test_generation_check_stays_disabled_until_javascript_initializes(self):
        soup = BeautifulSoup(str(generation.page()), "html.parser")
        fields = soup.select('.generation-form input[type="number"]')
        self.assertEqual(len(fields), 2)
        self.assertTrue(all(not field.has_attr("disabled") for field in fields))
        button = soup.select_one(".generation-submit")
        self.assertEqual(button["type"], "submit")
        self.assertTrue(button.has_attr("disabled"))
        self.assertEqual(button["form"], "generation-form")

    def test_gallery_uses_album_links_and_real_previews(self):
        soup = BeautifulSoup(str(gallery.page()), "html.parser")
        self.assertEqual(soup.select(".filter-tab"), [])
        self.assertEqual(soup.select_one(".gallery-count").get_text(strip=True), "4 альбома")
        self.assertEqual(
            {link["href"] for link in soup.select(".album-card")},
            {"/album/office", "/album/evening", "/album/street", "/album/study"},
        )
        self.assertEqual(len(soup.select(".album-image[src]")), 4)
        self.assertEqual(len(soup.select(".album-image[alt]")), 4)


if __name__ == "__main__":
    unittest.main()
