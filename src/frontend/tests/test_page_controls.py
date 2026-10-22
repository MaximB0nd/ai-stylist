import unittest

from bs4 import BeautifulSoup

from src.pages import feedback, gallery, generation, home, privacy, user_guide


class PageControlsTests(unittest.TestCase):
    def test_generation_has_only_real_account_flow(self):
        soup = BeautifulSoup(str(generation.page()), "html.parser")
        self.assertIsNone(soup.select_one("[data-demo-enabled], [data-auth-demo]"))
        notice = soup.select_one(".generation-launch-notice")
        self.assertTrue(notice.has_attr("hidden"))
        self.assertEqual(notice.select_one("a")["href"], "/gallery")

    def test_home_entry_points_use_protected_routes(self):
        soup = BeautifulSoup(str(home.page()), "html.parser")
        self.assertEqual(soup.select_one(".hero-actions .home-button")["href"], "/generation")
        self.assertEqual(soup.select_one(".hero-actions .home-gallery-button")["href"], "/gallery")
        self.assertEqual(soup.select_one(".site-sidebar a[href='/gallery']")["href"], "/gallery")

    def test_generation_submit_is_available_and_targets_the_questionnaire(self):
        soup = BeautifulSoup(str(generation.page()), "html.parser")
        fields = soup.select('.generation-form input[type="number"]')
        self.assertEqual(len(fields), 2)
        self.assertTrue(all(not field.has_attr("disabled") for field in fields))
        button = soup.select_one(".generation-submit")
        self.assertEqual(button["type"], "submit")
        self.assertFalse(button.has_attr("disabled"))
        self.assertEqual(button["form"], "generation-form")
        self.assertEqual(button.get_text(strip=True), "Сгенерировать")
        self.assertIsNotNone(soup.select_one(f'form#{button["form"]}'))

    def test_generation_style_labels_keep_existing_values(self):
        soup = BeautifulSoup(str(generation.page()), "html.parser")
        labels = {
            radio["value"]: radio.find_parent("label").get_text(strip=True)
            for radio in soup.select('[data-question="style"] input[type="radio"]')
        }
        self.assertEqual(labels["minimal"], "Базовый")
        self.assertEqual(labels["casual"], "Свободный")

    def test_gallery_waits_for_authenticated_album_data(self):
        soup = BeautifulSoup(str(gallery.page()), "html.parser")
        self.assertEqual(soup.select(".filter-tab"), [])
        self.assertEqual(soup.select(".album-card"), [])
        self.assertIsNotNone(soup.select_one("[data-gallery-grid]"))
        self.assertIsNotNone(soup.select_one("[data-gallery-message][role='status']"))

    def test_home_albums_wait_for_account_data(self):
        soup = BeautifulSoup(str(home.page()), "html.parser")
        self.assertEqual(soup.select(".albums-grid .album-card"), [])
        self.assertIsNotNone(soup.select_one("[data-home-albums-grid]"))
        self.assertIsNotNone(soup.select_one("[data-home-albums-state][role='status']"))
        self.assertIsNotNone(soup.select_one("[data-home-albums-action][hidden]"))
        self.assertIsNotNone(soup.select_one("[data-home-albums-link][hidden]"))

    def test_home_has_accessible_faq_disclosures(self):
        soup = BeautifulSoup(str(home.page()), "html.parser")
        items = soup.select(".home-faq__item")
        self.assertEqual(len(items), 12)
        self.assertTrue(all(item.select_one("summary") is not None for item in items))
        self.assertTrue(all(item.select_one(".home-faq__answer p") is not None for item in items))
        self.assertEqual(
            soup.select_one(".home-faq__heading .section-title").get_text(strip=True),
            "Вопросы и ответы",
        )
        self.assertIn("section-title", soup.select_one(".home-faq__heading h2")["class"])
        self.assertLess(
            list(soup.select(".home-page > section")).index(soup.select_one(".albums-section")),
            list(soup.select(".home-page > section")).index(soup.select_one(".home-faq")),
        )
        faq_copy = " ".join(item.get_text(" ", strip=True) for item in items).casefold()
        for implementation_note in ("сейчас нет", "демо-версии", "ещё не выполнено", "планируемая структура", "после подключения"):
            self.assertNotIn(implementation_note, faq_copy)

    def test_home_guide_uses_animated_illustrations_without_frame_overlays(self):
        soup = BeautifulSoup(str(home.page()), "html.parser")
        sections = list(soup.select(".home-page > section"))
        guide = soup.select_one(".home-guide")
        self.assertEqual(sections.index(guide) + 1, sections.index(soup.select_one(".albums-section")))
        self.assertEqual(guide.get("aria-label"), "Как работает сервис")
        self.assertEqual(guide.select(".home-guide__heading"), [])
        self.assertEqual(len(guide.select(".home-guide__step")), 3)
        self.assertEqual(
            [caption.get_text(strip=True) for caption in guide.select(".home-guide__caption")],
            ["Загрузите фото", "Выберите стиль", "Получите образы"],
        )
        self.assertEqual(len(guide.select(".home-guide__vika[data-animated-src][data-static-src]")), 3)
        self.assertEqual(guide.select(".home-guide__frame"), [])
        self.assertEqual(len(guide.select(".home-guide__arrow")), 2)
        arrow_sources = [arrow["src"] for arrow in guide.select("img.home-guide__arrow")]
        self.assertEqual(arrow_sources, ["/images/home/guide/designer-arrow.png"] * 2)
        self.assertEqual(guide.select(".home-guide__motion-toggle"), [])
        for scene in ("upload", "choose", "results"):
            self.assertEqual(len(guide.select(f".home-guide__vika--{scene}")), 1)
            image = guide.select_one(f".home-guide__vika--{scene}")
            self.assertTrue(image["data-animated-src"].endswith(".gif"))
            self.assertTrue(image["data-static-src"].endswith(".png"))

    def test_header_links_to_info_pages(self):
        soup = BeautifulSoup(str(generation.page()), "html.parser")
        self.assertEqual(
            {link.get_text(strip=True): link["href"] for link in soup.select(".site-header__nav a")},
            {
                "Политика": "/privacy",
                "Помощь": "/user-guide",
                "Контакты": "/feedback",
            },
        )

    def test_info_pages_render_project_sections(self):
        pages = (
            (privacy.page, "privacy-title", "Политика конфиденциальности"),
            (user_guide.page, "guide-title", "Помощь"),
            (feedback.page, "feedback-title", "Обратная связь"),
        )
        for render, heading_id, title in pages:
            with self.subTest(title=title):
                soup = BeautifulSoup(str(render()), "html.parser")
                self.assertEqual(soup.select_one(f"#{heading_id}").get_text(strip=True), title)
                self.assertIsNotNone(soup.select_one(".info-page"))


if __name__ == "__main__":
    unittest.main()
