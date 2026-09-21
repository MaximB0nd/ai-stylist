import unittest

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
                self.assertEqual(len(soup.select(".look-button")), 0)
                self.assertEqual(len(soup.select(".album-actions")), 0)

    def test_album_back_link_uses_shared_control(self):
        soup = BeautifulSoup(str(album.page()), "html.parser")
        back = soup.select_one(".album-back")
        self.assertEqual(back["href"], "/gallery")
        self.assertIn("ui-button", back["class"])

    def test_unknown_album_uses_fallback(self):
        soup = BeautifulSoup(str(album.page({"album_id": "missing"})), "html.parser")
        self.assertEqual(len(soup.select(".look-card")), 5)


if __name__ == "__main__":
    unittest.main()
