import unittest

from bs4 import BeautifulSoup

from src.pages import gallery, generation, home


class PageControlsTests(unittest.TestCase):
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
        self.assertEqual(len(soup.select(".album-card .album-image[src]")), 12)
        self.assertEqual(len(soup.select(".album-card .album-mosaic__primary[alt]")), 4)
        self.assertEqual(len(soup.select('.album-card .album-mosaic__secondary[alt=""]')), 8)
        layouts = {tuple(card.select_one(".album-mosaic")["class"]) for card in soup.select(".album-card")}
        self.assertEqual(len(layouts), 4)
        previews = {
            tuple(image["src"] for image in card.select(".album-mosaic__secondary"))
            for card in soup.select(".album-card")
        }
        self.assertEqual(len(previews), 4)

    def test_home_album_covers_use_three_photo_mosaics(self):
        soup = BeautifulSoup(str(home.page()), "html.parser")
        cards = soup.select(".albums-grid .album-card")
        self.assertEqual(len(cards), 3)
        self.assertTrue(all(len(card.select(".album-mosaic img")) == 3 for card in cards))
        layouts = {tuple(card.select_one(".album-mosaic")["class"]) for card in cards}
        self.assertEqual(len(layouts), 3)


if __name__ == "__main__":
    unittest.main()
