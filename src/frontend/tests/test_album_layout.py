import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup

from src.pages import album


class AlbumLayoutTests(unittest.TestCase):
    def test_albums_render_real_photo_cards(self):
        for album_id, (name, date) in album.ALBUMS.items():
            with self.subTest(album_id=album_id):
                soup = BeautifulSoup(str(album.page({"album_id": album_id})), "html.parser")
                self.assertEqual(soup.select_one("#album-title").text, name)
                self.assertEqual(soup.select_one("time").text, date)
                self.assertEqual(len(soup.select(".look-card")), 5)
                self.assertEqual(len(soup.select('.look-card img[src^="/images/album/"]')), 5)
                self.assertEqual(len(soup.select(".look-number")), 0)
                self.assertEqual(len(soup.select(".look-button")), 0)
                self.assertEqual(len(soup.select(".album-actions")), 0)

    def test_album_back_link_is_aligned_with_heading(self):
        soup = BeautifulSoup(str(album.page()), "html.parser")
        back = soup.select_one(".album-back")
        self.assertEqual(back["href"], "/gallery")
        self.assertIsNotNone(back.select_one(".site-icon--arrow-left"))
        self.assertIsNotNone(soup.select_one(".album-heading > .album-back"))
        self.assertIsNotNone(soup.select_one(".album-heading-copy > .album-date"))
        self.assertIsNotNone(soup.select_one(".album-details-trigger .site-icon--info"))

    def test_unknown_album_uses_fallback(self):
        soup = BeautifulSoup(str(album.page({"album_id": "missing"})), "html.parser")
        self.assertEqual(len(soup.select(".look-card")), 5)

    def test_album_details_panel_has_questionnaire_structure(self):
        soup = BeautifulSoup(str(album.page({"album_id": "office"})), "html.parser")
        trigger = soup.select_one("[data-album-details-trigger]")
        panel = soup.select_one("[data-album-details]")
        self.assertEqual(trigger["aria-controls"], panel["id"])
        self.assertEqual(len(panel.select("[data-album-choice]")), 4)
        self.assertEqual(len(panel.select("[data-album-photo]")), 2)
        self.assertEqual(len(panel.select("[data-album-fact]")), 3)
        self.assertEqual([heading.get_text(strip=True) for heading in panel.select("h2, h4")], ["Ваш выбор"])
        self.assertEqual(len(panel.select("figcaption")), 0)

    def test_real_album_waits_for_authenticated_api_data(self):
        album_id = "e1ad6314-c9ed-4921-a494-bbfa39745ca7"
        soup = BeautifulSoup(str(album.page({"album_id": album_id})), "html.parser")
        self.assertEqual(soup.select_one(".album-page")["data-album-id"], album_id)
        self.assertEqual(len(soup.select(".look-card")), 0)
        self.assertIsNotNone(soup.select_one("[data-album-looks-status]"))

    def test_album_preview_is_available_only_in_development(self):
        with patch.dict("os.environ", {"APP_ENV": "development"}):
            development = BeautifulSoup(str(album.page({"album_id": "office"})), "html.parser")
        with patch.dict("os.environ", {"APP_ENV": "production"}):
            production = BeautifulSoup(str(album.page({"album_id": "office"})), "html.parser")
        self.assertEqual(development.select_one(".album-page")["data-preview-enabled"], "true")
        self.assertEqual(production.select_one(".album-page")["data-preview-enabled"], "false")


if __name__ == "__main__":
    unittest.main()
