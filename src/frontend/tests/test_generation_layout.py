import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from bs4 import BeautifulSoup

from src.pages.generation import CHOICE_IMAGE_VERSION, CHOICES, page

FRONTEND = Path(__file__).resolve().parents[1]


class GenerationLayoutTests(unittest.TestCase):
    def setUp(self):
        self.soup = BeautifulSoup(str(page()), "html.parser")

    def test_measurement_constraints_match_the_reference(self):
        for key, minimum, maximum, step in (
            ("age", "1", "120", "1"),
            ("height", "80", "240", "1"),
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

    def test_choice_images_keep_text_labels_and_native_controls(self):
        for key, _, options in CHOICES:
            for value, label in options:
                with self.subTest(question=key, value=value):
                    field = self.soup.select_one(
                        f'input[name="{key}"][value="{value}"]'
                    )
                    card = field.find_parent("label")
                    self.assertIsNotNone(card)
                    self.assertEqual(card.get_text(strip=True), label)
                    self.assertEqual(field["type"], "radio")
                    self.assertFalse(field.has_attr("disabled"))
                    self.assertNotEqual(field.get("tabindex"), "-1")
                    image = card.select_one("img")
                    self.assertEqual(image.get("alt"), "")
                    self.assertEqual((image["width"], image["height"]), ("400", "400"))
                    self.assertEqual(
                        parse_qs(urlsplit(image["src"]).query),
                        {"v": [CHOICE_IMAGE_VERSION]},
                    )

    def test_photo_controls_are_separate_and_single_file(self):
        for key in ("body", "face"):
            with self.subTest(photo=key):
                card = self.soup.select_one(f'[data-photo="{key}"]')
                field = card.select_one('input[type="file"]')
                self.assertEqual(field["accept"], "image/jpeg,image/png,image/webp")
                self.assertFalse(field.has_attr("multiple"))
                self.assertEqual(field["aria-label"], card.label.get_text())
                media = card.select_one(".generation-photo-media")
                self.assertIsNotNone(media.select_one(".generation-preview"))
                self.assertIsNotNone(media.select_one(".generation-upload-actions"))
                for selector in ("[data-replace-photo]", "[data-remove-photo]"):
                    button = card.select_one(selector)
                    self.assertEqual(button["type"], "button")
                    self.assertTrue(button.has_attr("hidden"))
                self.assertTrue(card.select_one(".generation-preview").has_attr("hidden"))
                self.assertEqual(card.select_one(".generation-error")["role"], "alert")

    def test_error_references_resolve_and_ids_are_unique(self):
        ids = [element["id"] for element in self.soup.select("[id]")]
        self.assertEqual(len(ids), len(set(ids)))
        for element in self.soup.select("[aria-describedby]"):
            for reference in element["aria-describedby"].split():
                self.assertIsNotNone(self.soup.find(id=reference))
        self.assertEqual(len(self.soup.select(".generation-error[hidden]")), 8)

    def test_summary_has_no_fake_progress_or_generation(self):
        progress = self.soup.select_one("progress")
        self.assertEqual((progress["value"], progress["max"]), ("0", "8"))
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
        self.assertEqual(len(images), 18)
        for image in images:
            with self.subTest(src=image["src"]):
                self.assertTrue(image["src"].startswith("/images/generation/"))
                self.assertTrue(
                    (FRONTEND / "public" / urlsplit(image["src"]).path.lstrip("/")).is_file()
                )
                self.assertTrue(image.get("width"))
                self.assertTrue(image.get("height"))

    def test_compact_summary_does_not_repeat_empty_selections(self):
        summary = self.soup.select_one(".generation-summary")
        self.assertEqual(summary.h3.get_text(), "Ваш выбор")
        self.assertIsNone(summary.find("figure"))
        choices = summary.select_one(".generation-selections")
        self.assertTrue(choices.has_attr("hidden"))
        self.assertTrue(all(row.has_attr("hidden") for row in choices.select("div")))
        self.assertTrue(all(not value.get_text(strip=True) for value in choices.select("dd")))
        self.assertEqual(len(summary.select("[data-count]")), 1)
        self.assertIsNone(summary.select_one(".generation-checklist"))

    def test_visual_choices_precede_personal_details(self):
        self.assertIsNone(self.soup.select_one('[name="weight"]'))
        sections = self.soup.select(".generation-form > section")
        self.assertEqual(
            [section["aria-labelledby"] for section in sections],
            ["generation-questions-title", "generation-data-title"],
        )

    def test_personal_details_and_photos_share_one_section(self):
        about = self.soup.select_one(".generation-about")
        self.assertEqual(about.h3.get_text(strip=True), "О вас")
        self.assertEqual(
            self.soup.select_one("#generation-questions-title").get_text(), "Пожелания"
        )
        self.assertFalse(self.soup.select(".generation-section h3 span"))
        self.assertEqual(len(about.select('input[type="number"]')), 2)
        self.assertEqual(len(about.select('input[type="file"]')), 2)
        self.assertIsNotNone(about.select_one("#photo-formats"))

    def test_photo_examples_are_distinct_from_uploaded_photos(self):
        for key in ("body", "face"):
            photo = self.soup.select_one(f'[data-photo="{key}"]')
            empty = photo.select_one(".generation-photo-empty")
            self.assertFalse(empty.has_attr("hidden"))
            self.assertEqual(
                empty.select_one(".generation-example-label").get_text(), "Пример"
            )
            self.assertIn(f"photo-example-{key}.png", empty.img["src"])
            self.assertTrue(empty.img["alt"].startswith("Пример:"))
            self.assertEqual(empty.parent["for"], photo.select_one("input")["id"])
            self.assertFalse(photo.select_one(".generation-preview").has_attr("src"))

    def test_selection_thumbnails_are_real_edit_controls(self):
        for key, title, _ in CHOICES:
            button = self.soup.select_one(f'[data-edit-question="{key}"]')
            self.assertEqual(button["type"], "button")
            self.assertEqual(button["aria-label"], f"Изменить: {title}")
            self.assertIsNotNone(button.select_one(f'[data-selection="{key}"]'))
            image = button.img
            self.assertTrue(image.has_attr("hidden"))
            self.assertFalse(image.has_attr("src"))

    def test_photo_status_and_action_hierarchy_are_accessible(self):
        for photo in self.soup.select("[data-photo]"):
            for action, name in (("replace", "Заменить"), ("remove", "Удалить")):
                button = photo.select_one(f"[data-{action}-photo]")
                self.assertEqual(button.get_text(strip=True), "")
                self.assertEqual(button["title"], f"{name} фото")
                self.assertTrue(button["aria-label"].startswith(f"{name}:"))
                self.assertEqual(button.span["aria-hidden"], "true")
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
