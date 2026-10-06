from casp.layout import Metadata

from src.components.shared.layout.app_shell import app_shell

metadata = Metadata(title="Галерея", description="Примеры альбомов образов")

ALBUMS = (
    ("office", "Офис", "5 сентября 2026", "office.png", ("look02.png", "look04.png"), "left"),
    ("evening", "Вечер", "3 сентября 2026", "evening.png", ("look01.png", "look03.png"), "top"),
    ("street", "Улица", "1 сентября 2026", "street.png", ("look04.png", "look05.png"), "right"),
    ("study", "Учёба", "28 августа 2026", "study.png", ("look02.png", "look05.png"), "bottom"),
)


def page():
    cards = "".join(
        f"""
        <a href="/album/{slug}" class="album-card">
            <div class="album-preview">
              <div class="album-mosaic album-mosaic--{layout}">
                <img class="album-image album-mosaic__primary" src="/images/gallery/{image}" alt="{name}" width="640" height="640" loading="lazy" decoding="async">
                <img class="album-image album-mosaic__secondary" src="/images/album/{preview_images[0]}" alt="" width="640" height="960" loading="lazy" decoding="async">
                <img class="album-image album-mosaic__secondary" src="/images/album/{preview_images[1]}" alt="" width="640" height="960" loading="lazy" decoding="async">
              </div>
              <time class="album-date">{date}</time>
            </div>
          <div class="album-footer">
            <div class="album-meta">
              <h3 class="album-name">{name}</h3>
            </div>
            <span class="album-arrow" aria-hidden="true">↗</span>
          </div>
        </a>
        """
        for slug, name, date, image, preview_images, layout in ALBUMS
    )
    return app_shell(
        f"""
<section class="gallery-page" aria-labelledby="gallery-title">
  <div class="content-wrapper">
    <header class="gallery-header">
      <div>
        <h1 class="gallery-title" id="gallery-title">Галерея</h1>
      </div>
      <a href="/generation" class="btn-new-album ui-button"><span class="site-icon site-icon--plus btn-plus" aria-hidden="true"></span>Новые образы</a>
    </header>
    <div class="gallery-summary" aria-live="polite"><span class="gallery-count">{len(ALBUMS)} альбома</span></div>
    <div class="albums-grid">{cards}</div>
  </div>
</section>
""",
        title="Галерея",
        active_page="gallery",
    )
