from html import escape

from casp.layout import Metadata

from src.components.shared.layout.app_shell import app_shell
from src.data.home import HOME_ALBUMS

metadata = Metadata(
    title="Носи Красиво — ваш персональный стиль",
    description="Новый образ. Та же вы. Знакомство с виртуальной примеркой одежды и персональным стилем без походов по магазинам.",
)


def page():
    albums = "".join(
        f'''<a class="album-card" href="/album/{escape(album['slug'], quote=True)}">
          <div class="album-cover">
            <img class="album-image" src="/images/home/{escape(album['image'], quote=True)}.webp"
                 alt="{escape(album['alt'], quote=True)}" width="640" height="960" loading="lazy" decoding="async">
            <span class="album-open" aria-hidden="true">Открыть альбом ↗</span>
          </div>
          <div class="album-info">
            <div><h3 class="album-name">{escape(album['name'])}</h3>
              <p class="album-date">{escape(album['description'])}</p></div>
            <span class="album-arrow" aria-hidden="true">↗</span>
          </div>
        </a>'''
        for album in HOME_ALBUMS
    )
    return app_shell(
        f"""
<div class="home-page">
  <section class="hero" aria-labelledby="page-title">
    <div class="hero-content">
      <h2 class="hero-title" id="page-title">Ваш <span>стиль</span><br>начинается здесь</h2>
      <p class="hero-description">Персональный стилист для образов под ваш повод, настроение и особенности.</p>
      <div class="hero-actions">
        <a class="ui-button generate-button home-button" href="/generation">Найти свой образ</a>
      </div>
    </div>
    <figure class="hero-visual" aria-hidden="true">
      <div class="hero-showcase">
        <img class="hero-showcase__image" src="/images/home/hero-vika-loop.webp" data-motion-image data-animated-src="/images/home/hero-vika-loop.webp" data-static-src="/images/home/hero-vika-loop-static.png" alt="" width="1680" height="930" fetchpriority="high">
      </div>
    </figure>
  </section>

  <section class="albums-section" id="home-albums" aria-labelledby="home-albums-title">
    <div class="section-heading">
      <div><h2 class="section-title" id="home-albums-title">Альбомы</h2></div>
      <div class="section-aside">
        <a class="all-albums-link home-text-link" href="/gallery">Вся галерея <span aria-hidden="true">↗</span></a></div>
    </div>
    <div class="albums-grid">{albums}</div>
  </section>



</div>
""",
        title="Главная",
        active_page="home",
    )
