from html import escape

from casp.layout import Metadata

from src.components.shared.layout.app_shell import app_shell
from src.data.home import HOME_ALBUMS, HOME_FAQ

metadata = Metadata(
    title="Носи Красиво — ваш персональный стиль",
    description="Новый образ. Та же вы. Знакомство с виртуальной примеркой одежды и персональным стилем без походов по магазинам.",
)


def page():
    albums = "".join(
        f'''<a class="album-card" href="/album/{escape(album['slug'], quote=True)}">
          <div class="album-cover">
            <div class="album-mosaic album-mosaic--{escape(album['mosaic_layout'], quote=True)}">
              <img class="album-image album-mosaic__primary" src="/images/home/{escape(album['image'], quote=True)}.webp"
                   alt="{escape(album['alt'], quote=True)}" width="640" height="960" loading="lazy" decoding="async">
              <img class="album-image album-mosaic__secondary album-mosaic__secondary--one" src="/images/album/{escape(album['preview_images'][0], quote=True)}" alt="" width="640" height="960" loading="lazy" decoding="async">
              <img class="album-image album-mosaic__secondary album-mosaic__secondary--two" src="/images/album/{escape(album['preview_images'][1], quote=True)}" alt="" width="640" height="960" loading="lazy" decoding="async">
            </div>
          </div>
          <div class="album-info">
            <div><h3 class="album-name">{escape(album['name'])}</h3>
              <time class="album-date">{escape(album['description'])}</time></div>
          </div>
        </a>'''
        for album in HOME_ALBUMS
    )
    faq_items = "".join(
        f'''<details class="home-faq__item">
          <summary>
            <span class="home-faq__question">{escape(question)}</span>
            <span class="home-faq__indicator" aria-hidden="true"></span>
          </summary>
          <div class="home-faq__answer"><div class="home-faq__answer-inner"><p>{escape(answer)}</p></div></div>
        </details>'''
        for question, answer in HOME_FAQ
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

  <section class="home-guide" aria-label="Как работает сервис">
    <div class="home-guide__steps">
      <figure class="home-guide__step">
        <div class="home-guide__window">
          <img class="home-guide__vika home-guide__vika--upload" src="/images/home/guide/vika-upload-static.png" data-animated-src="/images/home/guide/vika-upload.gif" data-static-src="/images/home/guide/vika-upload-static.png" alt="Вика показывает фотографию на телефоне" width="1000" height="1200" decoding="async">
        </div>
        <figcaption class="home-guide__caption">Загрузите фото</figcaption>
      </figure>
      <img class="home-guide__arrow home-guide__arrow--first" src="/images/home/guide/designer-arrow.png" alt="" aria-hidden="true" width="960" height="480" decoding="async">
      <figure class="home-guide__step">
        <div class="home-guide__window">
          <img class="home-guide__vika home-guide__vika--choose" src="/images/home/guide/vika-choose-static.png" data-animated-src="/images/home/guide/vika-choose.gif" data-static-src="/images/home/guide/vika-choose-static.png" alt="Вика выбирает стиль по фотографиям одежды" width="1000" height="1200" decoding="async">
          <img class="home-guide__outfit-card home-guide__outfit-card--skirt" src="/images/home/guide/skirt.png" alt="" width="168" height="220" loading="lazy" decoding="async">
          <img class="home-guide__outfit-card home-guide__outfit-card--jacket" src="/images/home/guide/jacket.png" alt="" width="175" height="224" loading="lazy" decoding="async">
          <img class="home-guide__outfit-card home-guide__outfit-card--blouse" src="/images/home/guide/blouse.png" alt="" width="168" height="210" loading="lazy" decoding="async">
          <img class="home-guide__outfit-card home-guide__outfit-card--shoes" src="/images/home/guide/shoes.png" alt="" width="170" height="154" loading="lazy" decoding="async">
          <img class="home-guide__outfit-card home-guide__outfit-card--bag" src="/images/home/guide/bag.png" alt="" width="176" height="176" loading="lazy" decoding="async">
        </div>
        <figcaption class="home-guide__caption">Выберите стиль</figcaption>
      </figure>
      <img class="home-guide__arrow home-guide__arrow--second" src="/images/home/guide/designer-arrow.png" alt="" aria-hidden="true" width="960" height="480" decoding="async">
      <figure class="home-guide__step">
        <div class="home-guide__window">
          <img class="home-guide__vika home-guide__vika--results" src="/images/home/guide/vika-results-static.png" data-animated-src="/images/home/guide/vika-results.gif" data-static-src="/images/home/guide/vika-results-static.png" alt="Вика представляет готовые образы" width="1000" height="1200" decoding="async">
          <img class="home-guide__outfit-card home-guide__outfit-card--look-olive" src="/images/home/guide/look_olive.png" alt="" width="193" height="286" loading="lazy" decoding="async">
          <img class="home-guide__outfit-card home-guide__outfit-card--look-mauve" src="/images/home/guide/look_mauve.png" alt="" width="193" height="286" loading="lazy" decoding="async">
          <img class="home-guide__outfit-card home-guide__outfit-card--look-sage" src="/images/home/guide/look_sage.png" alt="" width="193" height="286" loading="lazy" decoding="async">
          <img class="home-guide__outfit-card home-guide__outfit-card--look-petrol" src="/images/home/guide/look_petrol.png" alt="" width="193" height="286" loading="lazy" decoding="async">
        </div>
        <figcaption class="home-guide__caption">Получите образы</figcaption>
      </figure>
    </div>
  </section>

  <section class="albums-section" id="home-albums" aria-labelledby="home-albums-title">
    <div class="section-heading">
      <div><h2 class="section-title" id="home-albums-title">Альбомы</h2></div>
      <div class="section-aside">
        <a class="all-albums-link home-text-link" href="/gallery">Вся галерея <span aria-hidden="true">↗</span></a></div>
    </div>
    <div class="albums-grid">{albums}</div>
  </section>

  <section class="home-faq" aria-labelledby="home-faq-title">
    <div class="section-heading home-faq__heading">
      <div><h2 class="section-title" id="home-faq-title">Вопросы и ответы</h2></div>
    </div>
    <div class="home-faq__layout">
      <div class="home-faq__list">{faq_items}</div>
      <figure class="home-faq__visual" aria-hidden="true">
        <img src="/images/home/faq-floral.png" alt="" />
      </figure>
    </div>
  </section>

</div>
""",
        title="Главная",
        active_page="home",
    )
