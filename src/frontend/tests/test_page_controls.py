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
        allowed_layouts = {"album-mosaic--left", "album-mosaic--right", "album-mosaic--left-compact", "album-mosaic--right-compact"}
        self.assertTrue(all(allowed_layouts.intersection(layout) for layout in layouts))
        previews = {
            tuple(image["src"] for image in card.select(".album-mosaic__secondary"))
            for card in soup.select(".album-card")
        }
        self.assertEqual(len(previews), 4)
        self.assertTrue(all(card.select_one(".album-preview .album-date") is None for card in soup.select(".album-card")))
        self.assertTrue(all(card.select_one(".album-footer time.album-date") is not None for card in soup.select(".album-card")))

    def test_home_album_covers_use_three_photo_mosaics(self):
        soup = BeautifulSoup(str(home.page()), "html.parser")
        cards = soup.select(".albums-grid .album-card")
        self.assertEqual(len(cards), 3)
        self.assertTrue(all(len(card.select(".album-mosaic img")) == 3 for card in cards))
        self.assertTrue(all(card.select_one("time.album-date") is not None for card in cards))
        layouts = {tuple(card.select_one(".album-mosaic")["class"]) for card in cards}
        self.assertEqual(len(layouts), 3)
        allowed_layouts = {"album-mosaic--left", "album-mosaic--right", "album-mosaic--left-compact", "album-mosaic--right-compact"}
        self.assertTrue(all(allowed_layouts.intersection(layout) for layout in layouts))

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


if __name__ == "__main__":
    unittest.main()
