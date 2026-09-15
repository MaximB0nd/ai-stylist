import unittest
from pathlib import Path

from bs4 import BeautifulSoup

from src.pages.generation import CHOICES, page

FRONTEND = Path(__file__).resolve().parents[1]


class GenerationLayoutTests(unittest.TestCase):
    def setUp(self):
        self.soup = BeautifulSoup(str(page()), "html.parser")

    def test_measurement_constraints_match_the_reference(self):
        for key, minimum, maximum, step in (
            ("age", "1", "120", "1"),
            ("height", "80", "240", "1"),
            ("weight", "20", "350", "0.1"),
        ):
            with self.subTest(field=key):
                field = self.soup.select_one(f"#generation-{key}")
                self.assertEqual(field["type"], "number")
                self.assertEqual(
                    (field["min"], field["max"], field["step"]),
                    (minimum, maximum, step),
                )
                self.assertTrue(field.has_attr("required"))
                self.assertFalse(field.has_attr("value"))
                self.assertIsNotNone(
                    self.soup.select_one(f'label[for="{field["id"]}"]')
                )

    def test_each_question_has_four_exclusive_options(self):
        self.assertEqual(len(self.soup.select("fieldset")), 4)
        for key, title, options in CHOICES:
            with self.subTest(question=key):
                group = self.soup.select_one(f'[data-question="{key}"]')
                self.assertEqual(group.legend.get_text(), title)
                inputs = group.select('input[type="radio"]')
                self.assertEqual(
                    {field["value"] for field in inputs},
                    {value for value, _ in options},
                )
                self.assertTrue(all(field["name"] == key for field in inputs))
                self.assertTrue(all(field.has_attr("required") for field in inputs))
                self.assertTrue(all(not field.has_attr("checked") for field in inputs))

    def test_photo_controls_are_separate_and_single_file(self):
        for key in ("body", "face"):
            with self.subTest(photo=key):
                card = self.soup.select_one(f'[data-photo="{key}"]')
                field = card.select_one('input[type="file"]')
                self.assertEqual(field["accept"], "image/jpeg,image/png,image/webp")
                self.assertFalse(field.has_attr("multiple"))
                for selector in ("[data-replace-photo]", "[data-remove-photo]"):
                    button = card.select_one(selector)
                    self.assertEqual(button["type"], "button")
                    self.assertTrue(button.has_attr("hidden"))
                self.assertTrue(card.select_one("img").has_attr("hidden"))
                self.assertEqual(card.select_one(".generation-error")["role"], "alert")

    def test_error_references_resolve_and_ids_are_unique(self):
        ids = [element["id"] for element in self.soup.select("[id]")]
        self.assertEqual(len(ids), len(set(ids)))
        for element in self.soup.select("[aria-describedby]"):
            for reference in element["aria-describedby"].split():
                self.assertIsNotNone(self.soup.find(id=reference))
        self.assertEqual(len(self.soup.select(".generation-error[hidden]")), 9)

    def test_summary_has_no_fake_progress_or_generation(self):
        progress = self.soup.select_one("progress")
        self.assertEqual((progress["value"], progress["max"]), ("0", "9"))
        self.assertEqual(len(self.soup.select("[data-selection]")), 4)
        button = self.soup.select_one(".generation-submit")
        self.assertEqual(button.get_text(strip=True), "Проверить анкету")
        self.assertTrue(button.has_attr("disabled"))
        self.assertEqual(button["form"], "generation-form")
        self.assertEqual(
            self.soup.select_one(".generation-status")["aria-live"], "polite"
        )

    def test_all_generation_images_are_local_and_present(self):
        images = self.soup.select(".generation-page img[src]")
        self.assertEqual(len(images), 16)
        for image in images:
            with self.subTest(src=image["src"]):
                self.assertTrue(image["src"].startswith("/images/generation/"))
                self.assertTrue(
                    (FRONTEND / "public" / image["src"].lstrip("/")).is_file()
                )
                self.assertTrue(image.get("width"))
                self.assertTrue(image.get("height"))

    def test_compact_summary_does_not_repeat_empty_selections(self):
        summary = self.soup.select_one(".generation-summary")
        self.assertEqual(summary.h3.get_text(), "Ваша анкета")
        self.assertIsNone(summary.find("figure"))
        choices = summary.select_one(".generation-selections")
        self.assertTrue(choices.has_attr("hidden"))
        self.assertTrue(all(row.has_attr("hidden") for row in choices.select("div")))
        self.assertTrue(all(not value.get_text() for value in choices.select("dd")))

    def test_photo_status_and_action_hierarchy_are_accessible(self):
        for photo in self.soup.select("[data-photo]"):
            status = photo.select_one("[data-photo-status]")
            self.assertEqual(status["role"], "status")
            self.assertEqual(status["aria-live"], "polite")
            self.assertIn(
                "ui-button--secondary",
                photo.select_one("[data-replace-photo]")["class"],
            )
            self.assertIn(
                "ui-button--quiet", photo.select_one("[data-remove-photo]")["class"]
            )


if __name__ == "__main__":
    unittest.main()
