from casp.layout import Metadata

from src.components.shared.layout.app_shell import app_shell

metadata = Metadata(title="Галерея", description="Примеры альбомов образов")

ALBUMS = (
    ("office", "Офис", "5 сентября 2026", "office.png"),
    ("evening", "Вечер", "3 сентября 2026", "evening.png"),
    ("street", "Улица", "1 сентября 2026", "street.png"),
    ("study", "Учёба", "28 августа 2026", "study.png"),
)


def page():
    cards = "".join(
        f"""
        <a href="/album/{slug}" class="album-card">
            <div class="album-preview">
              <img class="album-image" src="/images/gallery/{image}" alt="{name}" width="640" height="640" loading="lazy" decoding="async">
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
        for slug, name, date, image in ALBUMS
    )
    return app_shell(
        f"""
<section class="gallery-page" aria-labelledby="gallery-title">
  <div class="content-wrapper">
    <header class="gallery-header">
      <div>
        <h1 class="gallery-title" id="gallery-title">Галерея</h1>
      </div>
      <a href="/generation" class="btn-new-album ui-button"><span class="btn-plus" aria-hidden="true">+</span>Новые образы</a>
    </header>
    <div class="gallery-summary" aria-live="polite"><span class="gallery-count">{len(ALBUMS)} альбома</span></div>
    <div class="albums-grid">{cards}</div>
  </div>
</section>
""",
        title="Галерея",
        active_page="gallery",
    )
