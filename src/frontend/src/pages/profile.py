from casp.layout import Metadata

from src.components.shared.layout.app_shell import app_shell

metadata = Metadata(
    title="Профиль",
    description="Профиль и настройки Носи Красиво",
)


def page():
    return app_shell(
        """
<section class="profile-page" lang="ru" aria-label="Профиль и настройки">
  <div class="profile-layout">
    <div class="profile-main">
      <section class="profile-section profile-account" aria-labelledby="profile-account-title">
        <header class="profile-section__heading">
          <div>
            <p class="profile-caption">Аккаунт</p>
            <h3 id="profile-account-title">Данные профиля</h3>
          </div>
          <span class="profile-state">Не подключён</span>
        </header>

        <div class="profile-account__content">
          <div class="profile-avatar" aria-hidden="true">
            <span class="site-icon site-icon--user-round"></span>
          </div>
          <dl class="profile-fields">
            <div class="profile-field">
              <dt>Имя</dt>
              <dd data-profile-name>Не указано</dd>
            </div>
            <div class="profile-field">
              <dt>Электронная почта</dt>
              <dd data-profile-email>Не указана</dd>
            </div>
            <div class="profile-field">
              <dt>Профиль создан</dt>
              <dd data-profile-created>—</dd>
            </div>
          </dl>
        </div>
      </section>

      <section class="profile-section profile-settings" aria-labelledby="profile-settings-title">
        <header class="profile-section__heading">
          <div>
            <p class="profile-caption">Интерфейс</p>
            <h3 id="profile-settings-title">Настройки</h3>
          </div>
        </header>

        <div class="profile-settings__list">
          <label class="profile-setting">
            <span class="profile-setting__copy">
              <strong>Тёмная тема</strong>
              <small>Использовать тёмную палитру на всех страницах.</small>
            </span>
            <input type="checkbox" data-profile-preference="darkMode" />
            <span class="profile-toggle" aria-hidden="true"></span>
          </label>
          <label class="profile-setting">
            <span class="profile-setting__copy">
              <strong>Остановка анимации</strong>
              <small>Остановить GIF и отключить декоративные движения и переходы.</small>
            </span>
            <input type="checkbox" data-profile-preference="reduceMotion" />
            <span class="profile-toggle" aria-hidden="true"></span>
          </label>
        </div>
      </section>
    </div>

    <aside class="profile-guide" aria-labelledby="profile-guide-title">
      <div class="profile-guide__copy">
        <p class="profile-caption">Совет Вики</p>
        <h3 id="profile-guide-title">Начните с главного</h3>
        <p class="profile-guide__tip" data-vika-tip>
          Когда профиль будет подключён, имя и почта появятся здесь автоматически.
        </p>
      </div>
      <div class="profile-guide__visual" aria-hidden="true">
        <img
          src="/images/profile/vika-profile.gif"
          data-motion-image
          data-animated-src="/images/profile/vika-profile.gif"
          data-static-src="/images/profile/vika-profile-static.png"
          alt=""
          width="1254"
          height="1254"
        />
      </div>
    </aside>
  </div>
</section>
""",
        title="Профиль",
        active_page="profile",
    )
