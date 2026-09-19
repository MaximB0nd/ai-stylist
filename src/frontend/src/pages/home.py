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
              <p class="album-description">{escape(album['description'])}</p></div>
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
      <h2 class="hero-title" id="page-title">Новый образ.<br><em>Та же вы.</em></h2>
      <p class="hero-description">Чтобы найти своё, не нужно перемерять весь магазин. Идея проста: примерять одежду по фото и видеть себя в новом стиле.</p>
      <div class="hero-actions">
        <a class="generate-button home-button" href="/generation">Найти свой образ <span aria-hidden="true">↗</span></a>
        <a class="hero-gallery-link home-text-link" href="#home-albums" pp-spa="false">Посмотреть образы <span aria-hidden="true">↓</span></a>
      </div>
      </div>
    <figure class="hero-visual">
      <div class="hero-collage">
        <img class="collage-photo collage-photo--left" src="/images/home/hero-pink.webp" alt="Та же модель в розовой блузе и светлой юбке" width="640" height="960" decoding="async">
        <img class="collage-photo collage-photo--main" src="/images/home/hero-main.webp" alt="Модель в светлом брючном костюме" width="640" height="960" fetchpriority="high">
        <img class="collage-photo collage-photo--right" src="/images/home/hero-top.webp" alt="Та же модель в бордовом вечернем платье" width="640" height="960" decoding="async">
      </div>
    </figure>
  </section>

  <section class="albums-section" id="home-albums" aria-labelledby="home-albums-title">
    <div class="section-heading">
      <div><p class="home-eyebrow"></p>
        <h2 class="section-title" id="home-albums-title"></h2></div>
      <div class="section-aside"><p></p>
        <a class="all-albums-link home-text-link" href="/gallery">Вся галерея <span aria-hidden="true">↗</span></a></div>
    </div>
    <div class="albums-grid">{albums}</div>
  </section>

  <section class="home-approach" aria-labelledby="approach-title">
    <div class="approach-intro">
      <p class="home-eyebrow">В центре — вы</p>
      <h2 id="approach-title">Вам не нужно<br><em>становиться другой.</em></h2>
      <p>Наша идея — помочь увидеть, какая одежда вам близка. Сохранять внешность и находить новые сочетания, в которых вы узнаёте себя.</p>
      <a class="home-text-link" href="/generation">Познакомиться с анкетой <span aria-hidden="true">↗</span></a>
    </div>
    <ol class="home-steps" aria-label="Что учитывает анкета">
      <li><span class="step-number">01</span><div><h3>Начинаем с вас</h3><p>Фото и параметры вместо абстрактного образа на модели.</p></div></li>
      <li><span class="step-number">02</span><div><h3>Учитываем вашу жизнь</h3><p>Повод, настроение и любимый стиль задают направление подбора.</p></div></li>
      <li><span class="step-number">03</span><div><h3>Меняем только образ</h3><p>Одежда и сочетания помогают увидеть новые варианты своего стиля.</p></div></li>
    </ol>
  </section>

  <section class="home-faq" aria-labelledby="faq-title">
    <div><p class="home-eyebrow">Перед знакомством</p><h2 class="section-title" id="faq-title">Всё чуть проще,<br>чем кажется.</h2></div>
    <div class="faq-items">
      <details><summary>Что уже можно попробовать?<span aria-hidden="true">+</span></summary><p>Открыть примеры альбомов, заполнить анкету, добавить фотографии для предпросмотра и проверить данные. Генерация новых образов пока недоступна; данные анкеты не отправляются.</p></details>
      <details><summary>Вы меняете лицо или фигуру?<span aria-hidden="true">+</span></summary><p>Мы создаём сервис для примерки одежды, а не изменения внешности. Сохранение вашей внешности — ключевой принцип будущей примерки. Сейчас персональная генерация ещё в разработке.</p></details>
      <details><summary>Если я пока не знаю, какой стиль мне подходит?<span aria-hidden="true">+</span></summary><p>Начните с примеров и сравните, что вам ближе. Не нужно заранее знать названия стилей: ориентируйтесь на свой день, комфорт и настроение.</p></details>
      <details><summary>Фотографии на главной — это мой будущий результат?<span aria-hidden="true">+</span></summary><p>Это иллюстрации направлений стиля. Они помогают познакомиться с идеей сервиса, но не являются персональным результатом или гарантией будущего подбора.</p></details>
    </div>
  </section>

</div>
""",
        title="Главная",
        active_page="home",
    )
