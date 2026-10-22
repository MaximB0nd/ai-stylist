from casp.layout import Metadata
from html import escape

from src.components.shared.layout.app_shell import app_shell

metadata = Metadata(title="Альбом образов", description="Сохранённые образы")

def page(params=None):
    album_id = (params or {}).get("album_id", "")
    name = "Ваш альбом"
    album_id_attr = escape(album_id, quote=True)

    return app_shell(
        f"""
<section class="album-page" data-album-id="{album_id_attr}" aria-labelledby="album-title">
  <div class="content-wrapper">
    <header class="album-heading">
      <a href="/gallery" class="album-back" aria-label="Вернуться в галерею" title="Галерея"><span class="site-icon site-icon--arrow-left" aria-hidden="true"></span></a>
      <div class="album-heading-copy">
        <h1 class="album-title" id="album-title">{name}</h1>
        <time class="album-date" data-album-date></time>
      </div>
      <button class="album-details-trigger" type="button" data-album-details-trigger aria-label="Показать данные подбора" aria-haspopup="dialog" aria-expanded="false" aria-controls="album-details" title="О подборе"><span class="site-icon site-icon--info" aria-hidden="true"></span></button>
    </header>
    <p class="album-looks-status" data-album-looks-status>Загрузка образов…</p>
    <div class="looks-grid" data-looks-grid aria-label="Фотографии образов"></div>
  </div>
</section>
<aside class="album-details" id="album-details" data-album-details role="dialog" aria-labelledby="album-details-title" hidden>
  <div class="album-details-head">
    <h2 id="album-details-title">Ваш выбор</h2>
    <button type="button" class="album-details-close" data-album-details-close aria-label="Закрыть сведения об альбоме"></button>
  </div>
  <p class="album-details-status" data-album-details-status role="status" aria-live="polite"></p>
  <div class="album-details-content" data-album-details-content hidden>
    <section class="album-details-section" aria-label="Параметры подбора">
      <div class="album-details-choices">
        {''.join(f'<article class="album-details-choice" data-album-choice="{key}" aria-label="{title}"><div class="album-details-choice-card"><img alt="" hidden><span data-album-choice-label>Нет данных</span></div></article>' for key, title in (("occasion", "Куда?"), ("style", "Стиль"), ("shoe", "Обувь"), ("mood", "Впечатление")))}
      </div>
    </section>
    <section class="album-details-section" aria-label="Данные для образа">
      <dl class="album-details-facts"><div><dt>Возраст</dt><dd data-album-fact="age">Нет данных</dd></div><div><dt>Рост</dt><dd data-album-fact="height">Нет данных</dd></div><div><dt>Пол</dt><dd data-album-fact="gender">Нет данных</dd></div></dl>
    </section>
    <section class="album-details-section" aria-label="Исходные фотографии">
      <div class="album-details-photos">
        <figure data-album-photo="face" aria-label="Исходное фото лица"><div class="album-details-photo-frame"><img alt="Исходное фото лица" hidden><span>Фото недоступно</span></div></figure>
        <figure data-album-photo="body" aria-label="Исходное фото в полный рост"><div class="album-details-photo-frame"><img alt="Исходное фото в полный рост" hidden><span>Фото недоступно</span></div></figure>
      </div>
    </section>
  </div>
</aside>
<div class="album-lightbox" data-lightbox hidden>
  <button class="lightbox-close" type="button" data-lightbox-close aria-label="Закрыть"></button>
  <button class="lightbox-nav lightbox-prev" type="button" data-lightbox-prev aria-label="Предыдущий образ">←</button>
  <figure class="lightbox-figure">
    <img data-lightbox-image alt="">
    <figcaption><strong>{name}</strong><span class="lightbox-counter" data-lightbox-caption></span></figcaption>
  </figure>
  <button class="lightbox-nav lightbox-next" type="button" data-lightbox-next aria-label="Следующий образ">→</button>
</div>
""",
        title=name,
        active_page="gallery",
    )
