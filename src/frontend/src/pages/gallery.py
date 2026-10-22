from casp.layout import Metadata

from src.components.shared.layout.app_shell import app_shell

metadata = Metadata(title="Галерея", description="Ваши альбомы образов")


def page():
    return app_shell(
        """
<section class="gallery-page" aria-labelledby="gallery-title">
  <div class="content-wrapper">
    <header class="gallery-header">
      <h1 class="gallery-title" id="gallery-title">Галерея</h1>
      <a href="/generation" class="btn-new-album ui-button"><span class="site-icon site-icon--plus btn-plus" aria-hidden="true"></span>Новые образы</a>
    </header>
    <p class="gallery-message" data-gallery-message role="status" aria-live="polite">Загрузка альбомов…</p>
    <div class="albums-grid" data-gallery-grid></div>
  </div>
</section>
""",
        title="Галерея",
        active_page="gallery",
    )
