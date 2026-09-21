from casp.layout import Metadata

from src.components.shared.layout.app_shell import app_shell

metadata = Metadata(title="Альбом образов", description="Сохранённые образы")

ALBUMS = {
    "office": ("Офис", "5 сентября 2026"),
    "evening": ("Вечер", "3 сентября 2026"),
    "street": ("Улица", "1 сентября 2026"),
    "study": ("Учёба", "28 августа 2026"),
}


def page(params=None):
    album_id = (params or {}).get("album_id", "street")
    name, date = ALBUMS.get(album_id, ("Ваш альбом", "15 сентября 2026"))
    looks = "".join(
        f"""
        <button class="look-card" type="button" data-look-index="{index - 1}" aria-label="Открыть образ {index}">
          <div class="look-visual">
            <img src="/images/album/look{index:02d}.png" alt="Образ {index}" width="640" height="960" loading="lazy" decoding="async">
            <span class="look-number">{index:02d}</span>
          </div>
        </button>
        """
        for index in range(1, 6)
    )

    return app_shell(
        f"""
<section class="album-page" aria-labelledby="album-title">
  <div class="content-wrapper">
    <a href="/gallery" class="ui-button ui-button--quiet album-back" aria-label="Вернуться в галерею">← Галерея</a>
    <header class="album-heading">
      <div>
        <h1 class="album-title" id="album-title">{name}</h1>
        <div class="album-meta"><time>{date}</time><span aria-hidden="true">·</span><span>5 образов</span></div>
      </div>
    </header>
    <div class="looks-grid" aria-label="Фотографии образов">{looks}</div>
  </div>
</section>
<div class="album-lightbox" data-lightbox hidden>
  <button class="lightbox-close" type="button" data-lightbox-close aria-label="Закрыть">×</button>
  <button class="lightbox-nav lightbox-prev" type="button" data-lightbox-prev aria-label="Предыдущий образ">←</button>
  <figure class="lightbox-figure">
    <img data-lightbox-image alt="">
    <figcaption><strong>{name}</strong><span class="lightbox-counter" data-lightbox-caption></span></figcaption>
  </figure>
  <button class="lightbox-nav lightbox-next" type="button" data-lightbox-next aria-label="Следующий образ">→</button>
</div>
<script>
(() => {{
  const cards = [...document.querySelectorAll('.look-card')];
  const box = document.querySelector('[data-lightbox]');
  if (!cards.length || !box) return;
  const image = box.querySelector('[data-lightbox-image]');
  const caption = box.querySelector('[data-lightbox-caption]');
  let current = 0;
  const show = (index) => {{ current = (index + cards.length) % cards.length; const source = cards[current].querySelector('img'); image.src = source.src; image.alt = source.alt; caption.textContent = `Образ ${{current + 1}} из ${{cards.length}}`; box.hidden = false; document.body.classList.add('lightbox-open'); }};
  const close = () => {{ box.hidden = true; document.body.classList.remove('lightbox-open'); }};
  cards.forEach((card, index) => card.addEventListener('click', () => show(index)));
  box.querySelector('[data-lightbox-close]').addEventListener('click', close);
  box.querySelector('[data-lightbox-prev]').addEventListener('click', () => show(current - 1));
  box.querySelector('[data-lightbox-next]').addEventListener('click', () => show(current + 1));
  box.addEventListener('click', (event) => {{ if (event.target === box) close(); }});
  document.addEventListener('keydown', (event) => {{ if (box.hidden) return; if (event.key === 'Escape') close(); if (event.key === 'ArrowLeft') show(current - 1); if (event.key === 'ArrowRight') show(current + 1); }});
}})();
</script>
""",
        title=name,
        active_page="gallery",
    )
