import unittest
from pathlib import Path

from bs4 import BeautifulSoup

from src.pages import profile


class ProfileLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.soup = BeautifulSoup(str(profile.page()), "html.parser")
        cls.public_root = Path(__file__).resolve().parents[1] / "public"

    def test_profile_uses_vertical_vika_panel(self):
        guide = self.soup.select_one(".profile-guide")
        image = guide.select_one("img")
        self.assertEqual(image["src"], "/images/profile/vika-profile.gif")
        self.assertEqual(
            image["data-static-src"],
            "/images/profile/vika-profile-static.png",
        )
        self.assertEqual((image["width"], image["height"]), ("1254", "1254"))
        self.assertTrue((self.public_root / image["src"].removeprefix("/")).is_file())
        self.assertTrue(
            (self.public_root / image["data-static-src"].removeprefix("/")).is_file()
        )

    def test_profile_has_neutral_account_placeholders(self):
        values = [item.get_text(strip=True) for item in self.soup.select(".profile-field dd")]
        self.assertEqual(values, ["Не указано", "Не указана", "—"])
        self.assertNotIn("Анна", self.soup.get_text())
        self.assertNotIn("example.com", self.soup.get_text())

    def test_profile_contains_frontend_preferences_only(self):
        settings = self.soup.select("[data-profile-preference]")
        self.assertEqual(
            [setting["data-profile-preference"] for setting in settings],
            ["darkMode", "reduceMotion"],
        )

    def test_profile_has_no_generation_actions(self):
        self.assertIsNone(self.soup.select_one('.profile-page a[href="/generation"]'))
        self.assertIsNone(self.soup.select_one(".profile-actions"))


if __name__ == "__main__":
    unittest.main()
