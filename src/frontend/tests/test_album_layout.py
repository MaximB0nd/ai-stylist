import unittest

from bs4 import BeautifulSoup

from src.pages import album


class AlbumLayoutTests(unittest.TestCase):
    def test_all_demo_albums_keep_their_content(self):
        for album_id, data in album.ALBUMS.items():
            with self.subTest(album_id=album_id):
                soup = BeautifulSoup(
                    str(album.page({"album_id": album_id})), "html.parser"
                )
                self.assertEqual(soup.select_one("#album-title").text, data["name"])
                self.assertEqual(soup.select_one("time").text, data["date"])
                self.assertEqual(
                    [tag.text for tag in soup.select(".context-chip")], data["tags"]
                )
                looks = soup.select(".look-button")
                self.assertEqual(len(looks), 5)
                self.assertTrue(all(look["type"] == "button" for look in looks))
                self.assertEqual(len(soup.select(".look-visual[role=img]")), 5)
                self.assertEqual(
                    len(soup.select(".tag")), 2 if data.get("archived") else 1
                )

    def test_album_actions_use_shared_controls(self):
        soup = BeautifulSoup(str(album.page()), "html.parser")
        back = soup.select_one(".album-back")
        self.assertEqual(back["href"], "/gallery")
        self.assertIn("ui-button", back["class"])
        self.assertIn("ui-button--quiet", back["class"])
        actions = soup.select(".album-actions button")
        self.assertEqual(len(actions), 2)
        self.assertTrue(all("ui-button" in button["class"] for button in actions))
        self.assertTrue(all(button["type"] == "button" for button in actions))
        self.assertIn("ui-button--secondary", actions[0]["class"])
        self.assertIn("ui-button--quiet", actions[1]["class"])

    def test_unknown_album_still_uses_the_existing_fallback(self):
        soup = BeautifulSoup(
            str(album.page({"album_id": "missing"})), "html.parser"
        )
        self.assertEqual(len(soup.select(".look-button")), 5)
        current = soup.select_one('.site-sidebar [aria-current="page"]')
        self.assertEqual(current["href"], "/gallery")


if __name__ == "__main__":
    unittest.main()
