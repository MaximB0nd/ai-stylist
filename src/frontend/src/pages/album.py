from casp.layout import Metadata

from src.components.shared.layout.app_shell import app_shell

metadata = Metadata(
    title="Альбом образов",
    description="Фотографии образов из одного альбома",
)


ALBUMS = {
    "office": {
        "name": "Офис",
        "date": "5 сентября 2026",
        "tags": ["Минимализм", "Лоферы", "Уверенное"],
    },
    "evening": {
        "name": "Вечер",
        "date": "3 сентября 2026",
        "tags": ["Классика", "Каблук", "Элегантное"],
    },
    "street": {
        "name": "Улица",
        "date": "1 сентября 2026",
        "tags": ["Casual", "Кроссовки", "Расслабленное"],
    },
    "study": {
        "name": "Учёба",
        "date": "28 августа 2026",
        "tags": ["Классика", "Лоферы", "Элегантное"],
        "archived": True,
    },
}


def page(params=None):
    album_id = (params or {}).get("album_id", "street")
    album = ALBUMS.get(
        album_id,
        {
            "name": "Ваш альбом",
            "date": "15 сентября 2026",
            "tags": ["Персональный", "Демо", "5 образов"],
        },
    )
    tags = album.get("tags", [])
    archived = album.get("archived", False)

    context = "\n".join(
        f'<span class="context-chip">{tag}</span>'
        for tag in tags
    )

    looks = "\n".join(
        f"""
        <button class="look-button" type="button" aria-label="Открыть образ {index}">
          <span class="look-visual look-visual--{index}" role="img" aria-label="Демо-фотография образа {index}">
            <span class="look-expand" aria-hidden="true">⌕</span>
          </span>
          <span class="look-caption">
            <span>Образ</span>
            <b>{str(index).zfill(2)}</b>
          </span>
        </button>
        """
        for index in range(1, 6)
    )

    return app_shell(
        f"""
<section class="album-page" aria-labelledby="album-title">
  <div class="content-wrapper">
    <a href="/gallery" class="ui-button ui-button--quiet album-back" aria-label="Вернуться в галерею">← Назад в галерею</a>

    <div class="page-heading album-heading">
      <div>
        <h1 class="album-title" id="album-title">{album["name"]}</h1>
        <div class="album-meta">
          <time>{album["date"]}</time>
          <span class="meta-dot"></span>
          <span>5 образов</span>
          <span class="tag">Демоальбом</span>
          {'<span class="tag">В архиве</span>' if archived else ''}
        </div>
      </div>

      <div class="album-actions">
        <button class="ui-button ui-button--secondary" type="button">Архивировать</button>
        <button class="ui-button ui-button--quiet" type="button">Удалить</button>
      </div>
    </div>

    <div class="look-context" aria-label="Параметры альбома">
      {context}
    </div>

    <div class="looks-grid" aria-label="Фотографии образов">
      {looks}
    </div>

    <p class="album-note">Пять демо-образов из одной генерации</p>
  </div>
</section>
""",
        title=album["name"],
        active_page="gallery",
    )
