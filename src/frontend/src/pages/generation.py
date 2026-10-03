from casp.layout import Metadata

from src.components.shared.layout.app_shell import app_shell

metadata = Metadata(
    title="Новые образы",
    description="Заполните данные для генерации образов",
)

# Bump when replacing choice assets so browsers revalidate the illustrations.
CHOICE_IMAGE_VERSION = "3"

CHOICES = (
    (
        "occasion",
        "Куда?",
        (
            ("street", "Улица"),
            ("study", "Учёба"),
            ("office", "Офис"),
            ("evening", "Вечер"),
        ),
    ),
    (
        "style",
        "Стиль",
        (
            ("minimal", "Минимализм"),
            ("classic", "Классика"),
            ("casual", "Casual"),
            ("romantic", "Романтика"),
        ),
    ),
    (
        "shoe",
        "Обувь",
        (
            ("sneakers", "Кроссовки"),
            ("loafers", "Лоферы"),
            ("heels", "Каблук"),
            ("boots", "Ботинки"),
        ),
    ),
    (
        "mood",
        "Впечатление",
        (
            ("confident", "Уверенное"),
            ("elegant", "Элегантное"),
            ("relaxed", "Уютное"),
            ("bright", "Яркое"),
        ),
    ),
)


def _measurements():
    fields = (
        ("age", "Возраст, лет", 1, 120, "1", "28"),
        ("height", "Рост, см", 80, 240, "1", "168"),
    )
    return "".join(
        f"""
<div class="generation-field">
  <label for="generation-{key}">{label}</label>
  <input class="ui-input" id="generation-{key}" type="number" name="{key}"
    min="{minimum}" max="{maximum}" step="{step}" placeholder="{placeholder}"
    required autocomplete="off" aria-describedby="{key}-error" />
  <p class="generation-error" id="{key}-error" hidden></p>
</div>"""
        for key, label, minimum, maximum, step, placeholder in fields
    )


def _gender_field():
    options = (
        ("male", "Мужской"),
        ("female", "Женский"),
    )
    choices = "".join(
        f"""
<label class="generation-gender-option">
  <input type="radio" name="gender" value="{value}" required />
  <span>{label}</span>
</label>"""
        for value, label in options
    )
    return f"""
<fieldset class="generation-gender" data-personal-question="gender" aria-describedby="gender-error">
  <legend>Пол</legend>
  <div class="generation-gender-options">{choices}</div>
  <p class="generation-error" id="gender-error" hidden></p>
</fieldset>"""


def _uploads():
    return "".join(
        f"""
<div class="generation-upload" data-photo="{key}">
  <label for="generation-{key}">{label}</label>
  <div class="generation-photo-media">
  <label class="generation-upload-slot" for="generation-{key}">
    <span class="generation-photo-empty">
      <span class="generation-photo-example">
        <img src="/images/generation/photo-example-{key}.png" width="1254" height="1254"
          alt="{example}" loading="lazy" />
        <span class="generation-example-label">Пример</span>
      </span>
      <span class="generation-upload-prompt">
        <span class="site-icon site-icon--images" aria-hidden="true"></span>
        Добавить фото
      </span>
    </span>
    <img class="generation-preview" alt="{label}" hidden />
  </label>
  <input id="generation-{key}" type="file" name="{key}"
    accept="image/jpeg,image/png,image/webp" aria-label="{label}"
    aria-describedby="photo-formats {key}-error" />
  <div class="generation-upload-actions">
    <button class="ui-button ui-button--secondary" type="button" data-replace-photo hidden
      aria-label="Заменить: {label}" title="Заменить фото">
      <span class="site-icon generation-icon-pencil" aria-hidden="true"></span>
    </button>
    <button class="ui-button ui-button--quiet" type="button" data-remove-photo hidden
      aria-label="Удалить: {label}" title="Удалить фото">
      <span class="site-icon generation-icon-trash" aria-hidden="true"></span>
    </button>
  </div>
  </div>
  <p class="generation-photo-status" data-photo-status role="status" aria-live="polite"></p>
  <p class="generation-error" id="{key}-error" role="alert" hidden></p>
</div>"""
        for key, label, example in (
            ("face", "Фото лица", "Пример: лицо анфас и плечи"),
            ("body", "Фото в полный рост", "Пример: человек целиком, от головы до стоп"),
        )
    )


def _questions():
    groups = []
    for key, title, options in CHOICES:
        cards = "".join(
            f"""
<label class="generation-choice">
  <input type="radio" name="{key}" value="{value}" required />
  <span class="generation-choice-card">
    <img src="/images/generation/{key}-{value}.webp?v={CHOICE_IMAGE_VERSION}" width="400" height="400" alt="" loading="lazy" />
    <span>{label}</span>
  </span>
</label>"""
            for value, label in options
        )
        groups.append(f"""
<fieldset class="generation-question" data-question="{key}" aria-describedby="{key}-error">
  <legend>{title}</legend>
  <div class="generation-card-grid">{cards}</div>
  <p class="generation-error" id="{key}-error" hidden></p>
</fieldset>""")
    return "".join(groups)


def _selections():
    return "".join(
        f"""
<div class="is-empty" data-summary-item="{key}">
  <dt class="visually-hidden">{title}</dt>
  <dd>
    <div class="generation-selection" aria-hidden="true">
      <img data-selection-image="{key}" width="80" height="80" alt="" hidden />
      <span class="visually-hidden" data-selection="{key}"></span>
    </div>
  </dd>
</div>"""
        for key, title, _ in CHOICES
    )


def page():
    return app_shell(
        f"""
<section class="generation-page" aria-labelledby="generation-title">
  <div class="generation-heading">
    <h2 id="generation-title">Новые образы</h2>
  </div>
  <section class="generation-intro" aria-labelledby="generation-intro-title">
    <div class="generation-intro-visual" aria-hidden="true">
      <img
        src="/images/generation/vika-adviser.gif"
        data-motion-image
        data-animated-src="/images/generation/vika-adviser.gif"
        data-static-src="/images/generation/vika-adviser-static.png"
        alt=""
        width="1254"
        height="1254"
      />
    </div>
    <div class="generation-intro-copy">
      <h3 id="generation-intro-title"><span>Вика</span> поможет собрать образ</h3>
      <p>
        Расскажите, куда вы собираетесь и что вам нравится — Вика подберёт
        образ именно для вас.
      </p>
    </div>
    <div class="generation-intro-details" aria-hidden="true">
      <img src="/images/generation/intro-street-walk.webp" alt="" width="512" height="512" />
      <img src="/images/generation/intro-conference-women.webp" alt="" width="512" height="512" />
    </div>
  </section>
  <div class="generation-layout">
    <form class="generation-form" id="generation-form" novalidate>
      <section class="generation-section" aria-labelledby="generation-questions-title">
        <h3 class="visually-hidden" id="generation-questions-title">Пожелания</h3>
        <div class="generation-questions">{_questions()}</div>
      </section>
      <section class="generation-section generation-about" aria-labelledby="generation-data-title">
        <h3 class="visually-hidden" id="generation-data-title">Данные для образа</h3>
        <div class="generation-about-layout">
          <div class="generation-measurements">{_measurements()}{_gender_field()}</div>
          <div class="generation-photos">
            <div class="generation-uploads">{_uploads()}</div>
            <p class="generation-note" id="photo-formats">JPG, PNG, WebP · до 10 МБ на фото</p>
          </div>
        </div>
      </section>
    </form>
    <aside class="generation-summary" aria-labelledby="generation-summary-title">
      <h3 id="generation-summary-title">Ваш выбор</h3>
      <dl class="generation-selections">
        {_selections()}
      </dl>
      <p class="generation-status" role="status" aria-live="polite"></p>
      <div class="generation-progress-label"><label for="generation-progress">Заполнено</label><span data-count="total">0 / 9</span></div>
      <progress id="generation-progress" value="0" max="9">0 из 9</progress>
      <button class="generation-submit generation-generate ui-button" type="submit" form="generation-form">
        Сгенерировать
      </button>
    </aside>
  </div>
</section>
""",
        title="Новые образы",
        active_page="generation",
    )
