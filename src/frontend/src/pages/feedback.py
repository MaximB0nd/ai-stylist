from casp.layout import Metadata

from src.components.shared.layout.app_shell import app_shell

metadata = Metadata(
    title="Обратная связь — Носи Красиво",
    description="Страница обратной связи для вопросов и предложений по сайту Носи Красиво.",
)


def page():
    return app_shell(
        """
<section class="info-page feedback-page" aria-labelledby="feedback-title">
  <div class="info-hero">
    <h2 id="feedback-title">Обратная связь</h2>
  </div>

  <div class="feedback-layout">
    <form class="feedback-form" aria-label="Форма обратной связи">
      <label>
        Ваше имя
        <input class="ui-input" type="text" name="name" autocomplete="name" placeholder="Анна">
      </label>
      <label>
        Почта для ответа
        <input class="ui-input" type="email" name="email" autocomplete="email" placeholder="you@example.com">
      </label>
      <label>
        Сообщение
        <textarea class="ui-input feedback-message" name="message" rows="4" placeholder="Коротко опишите вопрос или идею"></textarea>
      </label>
      <button class="ui-button feedback-submit" type="button">Отправить</button>
    </form>

    <aside class="feedback-side" aria-hidden="true">
      <figure class="feedback-vika" aria-hidden="true">
        <img
          src="/images/feedback/vika-feedback-contact.gif"
          data-motion-image
          data-animated-src="/images/feedback/vika-feedback-contact.gif"
          data-static-src="/images/feedback/vika-feedback-contact-static.png"
          alt=""
          width="1166"
          height="1349"
          loading="lazy"
        />
      </figure>
    </aside>
  </div>
</section>
""",
        title="Обратная связь",
        active_page="feedback",
    )
