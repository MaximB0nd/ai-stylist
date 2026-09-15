from casp.layout import Metadata

from src.components.shared.layout.app_shell import app_shell

metadata = Metadata(
    title="Новые образы",
    description="Заполните данные для генерации образов",
)

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
            ("romantic", "Романтичный"),
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
            ("relaxed", "Расслабленное"),
            ("bright", "Яркое"),
        ),
    ),
)


def _measurements():
    fields = (
        ("age", "Возраст, лет", 1, 120, "1", "28"),
        ("height", "Рост, см", 80, 240, "1", "168"),
        ("weight", "Вес, кг", 20, 350, "0.1", "58"),
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


def _uploads():
    return "".join(
        f"""
<div class="generation-upload" data-photo="{key}">
  <label for="generation-{key}">{label}</label>
  <label class="generation-upload-slot" for="generation-{key}">
    <span class="generation-photo-empty">
      <span class="site-icon site-icon--images" aria-hidden="true"></span>
      <span>Добавить фото</span>
    </span>
    <img class="generation-preview" alt="{label}" hidden />
  </label>
  <input id="generation-{key}" type="file" name="{key}"
    accept="image/jpeg,image/png,image/webp" aria-describedby="photo-formats {key}-error" />
  <div class="generation-upload-actions">
    <button class="ui-button ui-button--quiet" type="button" data-replace-photo hidden>Заменить</button>
    <button class="ui-button ui-button--quiet" type="button" data-remove-photo hidden
      aria-label="Удалить: {label}">Удалить</button>
  </div>
  <p class="generation-error" id="{key}-error" role="alert" hidden></p>
</div>"""
        for key, label in (("body", "Фото в полный рост"), ("face", "Фото лица"))
    )


def _questions():
    groups = []
    for key, title, options in CHOICES:
        cards = "".join(
            f"""
<label class="generation-choice">
  <input type="radio" name="{key}" value="{value}" required />
  <span class="generation-choice-card">
    <img src="/images/generation/{key}-{value}.webp" width="400" height="400" alt="" loading="lazy" />
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


def page():
    return app_shell(
        f"""
<section class="generation-page" aria-labelledby="generation-title">
  <div class="generation-heading">
    <h2 id="generation-title">Новые образы</h2>
    <p>Ваши параметры и пожелания к новому образу.</p>
  </div>
  <div class="generation-layout">
    <form class="generation-form" id="generation-form" novalidate>
      <section class="generation-section" aria-labelledby="generation-data-title">
        <h3 id="generation-data-title"><span>01</span> Немного о вас</h3>
        <div class="generation-measurements">{_measurements()}</div>
      </section>
      <section class="generation-section" aria-labelledby="generation-photo-title">
        <h3 id="generation-photo-title"><span>02</span> Две фотографии</h3>
        <div class="generation-uploads">{_uploads()}</div>
        <p class="generation-note" id="photo-formats">JPG, PNG, WebP · до 10 МБ на фото</p>
      </section>
      <section class="generation-section" aria-labelledby="generation-questions-title">
        <h3 id="generation-questions-title"><span>03</span> Параметры образа</h3>
        <div class="generation-questions">{_questions()}</div>
      </section>
    </form>
    <aside class="generation-summary" aria-labelledby="generation-summary-title">
      <figure>
        <img src="/images/generation/photo06.webp" alt="Пример сочетания одежды для вдохновения" width="400" height="300" />
        <figcaption>Вдохновение</figcaption>
      </figure>
      <h3 id="generation-summary-title">Ваш альбом</h3>
      <dl class="generation-selections">
        {"".join(f'<div><dt>{title}</dt><dd data-selection="{key}">Не выбрано</dd></div>' for key, title, _ in CHOICES)}
      </dl>
      <dl class="generation-checklist">
        <div><dt>Параметры</dt><dd data-count="measurements">0 / 3</dd></div>
        <div><dt>Фотографии</dt><dd data-count="photos">0 / 2</dd></div>
        <div><dt>Пожелания</dt><dd data-count="choices">0 / 4</dd></div>
      </dl>
      <div class="generation-progress-label"><label for="generation-progress">Заполнено</label><span data-count="total">0 / 9</span></div>
      <progress id="generation-progress" value="0" max="9">0 из 9</progress>
      <button class="generation-submit ui-button" type="submit" form="generation-form" disabled>
        Проверить анкету
      </button>
      <p class="generation-note">Генерация образов пока недоступна. Фото и параметры не отправляются на сервер.</p>
      <p class="generation-status" role="status" aria-live="polite"></p>
    </aside>
  </div>
</section>
""",
        title="Новые образы",
        active_page="generation",
    )
