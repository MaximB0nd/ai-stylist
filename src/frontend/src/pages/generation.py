from casp.layout import Metadata

from src.components.shared.layout.app_shell import app_shell

metadata = Metadata(
    title="Новые образы",
    description="Заполните данные для генерации образов",
)


def page():
    return app_shell(
        r"""
<section class="generation-page">
  <section class="generation-heading" aria-labelledby="generation-title">
    <h2 id="generation-title">Новые образы</h2>
    <p>Заполните данные и пожелания для генерации.</p>
  </section>

  <form class="generation-form">
    <section class="generation-frame generation-data-frame" aria-labelledby="generation-data-title">
      <div class="generation-frame-header">
        <h2 id="generation-data-title">Данные для генерации</h2>
      </div>

      <div class="generation-fields generation-fields-three">
        <label for="generation-age">
          Возраст
          <input id="generation-age" type="number" name="age" min="1" value="28" />
        </label>

        <label for="generation-height">
          Рост, см
          <input id="generation-height" type="number" name="height" min="1" value="168" />
        </label>

        <label for="generation-weight">
          Вес, кг
          <input id="generation-weight" type="number" name="weight" min="1" value="56" />
        </label>
      </div>

      <div class="generation-fields generation-fields-two">
        <div class="generation-upload-frame">
          <span>Фото в полный рост</span>
          <span class="generation-upload-slot">Зона фото</span>
        </div>

        <div class="generation-upload-frame">
          <span>Фото лица</span>
          <span class="generation-upload-slot">Зона фото</span>
        </div>
      </div>
    </section>

    <div class="generation-question-grid" aria-label="Анкета">
      <section class="generation-frame" aria-labelledby="occasion-title">
        <h2 id="occasion-title">Куда?</h2>

        <div class="generation-card-grid">
          <div class="generation-choice-card">
            <span>Улица</span>
          </div>

          <div class="generation-choice-card">
            <span>Учёба</span>
          </div>

          <div class="generation-choice-card">
            <span>Офис</span>
          </div>

          <div class="generation-choice-card">
            <span>Вечер</span>
          </div>
        </div>
      </section>

      <section class="generation-frame" aria-labelledby="style-title">
        <h2 id="style-title">Стиль</h2>

        <div class="generation-card-grid">
          <div class="generation-choice-card">
            <span>Минимализм</span>
          </div>

          <div class="generation-choice-card">
            <span>Классика</span>
          </div>

          <div class="generation-choice-card">
            <span>Casual</span>
          </div>

          <div class="generation-choice-card">
            <span>Романтичный</span>
          </div>
        </div>
      </section>

      <section class="generation-frame" aria-labelledby="shoes-title">
        <h2 id="shoes-title">Обувь</h2>

        <div class="generation-card-grid">
          <div class="generation-choice-card">
            <span>Кроссовки</span>
          </div>

          <div class="generation-choice-card">
            <span>Лоферы</span>
          </div>

          <div class="generation-choice-card">
            <span>Каблук</span>
          </div>

          <div class="generation-choice-card">
            <span>Ботинки</span>
          </div>
        </div>
      </section>

      <section class="generation-frame" aria-labelledby="mood-title">
        <h2 id="mood-title">Впечатление</h2>

        <div class="generation-card-grid">
          <div class="generation-choice-card">
            <span>Уверенное</span>
          </div>

          <div class="generation-choice-card">
            <span>Элегантное</span>
          </div>

          <div class="generation-choice-card">
            <span>Расслабленное</span>
          </div>

          <div class="generation-choice-card">
            <span>Яркое</span>
          </div>
        </div>
      </section>
    </div>

    <div class="generation-actions">
      <button class="generation-submit" type="button">
        Сгенерировать 5 образов
      </button>
    </div>
  </form>
</section>
""",
        title="Новые образы",
    )
