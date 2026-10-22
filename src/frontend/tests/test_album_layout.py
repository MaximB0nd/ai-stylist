import unittest

from bs4 import BeautifulSoup

from src.pages import album


class AlbumLayoutTests(unittest.TestCase):
    def test_album_waits_for_authenticated_photo_data(self):
        soup = BeautifulSoup(str(album.page({"album_id": "office"})), "html.parser")
        self.assertEqual(soup.select_one("#album-title").text, "Ваш альбом")
        self.assertEqual(soup.select(".look-card"), [])
        self.assertEqual(soup.select('.look-card img[src^="/images/album/"]'), [])

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
        self.assertEqual(len(soup.select(".look-card")), 0)

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

    def test_album_never_embeds_preview_data(self):
        soup = BeautifulSoup(str(album.page({"album_id": "office"})), "html.parser")
        self.assertIsNone(soup.select_one("[data-preview-enabled]"))
        self.assertIsNone(soup.select_one(".look-card"))


if __name__ == "__main__":
    unittest.main()
