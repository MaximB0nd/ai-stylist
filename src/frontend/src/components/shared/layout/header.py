from html import escape


def header(title="Носи Красиво", active_page=None):
    safe_title = escape(str(title))
    nav_items = (
        ("privacy", "/privacy", "Политика"),
        ("user-guide", "/user-guide", "Помощь"),
        ("feedback", "/feedback", "Контакты"),
    )
    nav_links = ""
    for key, href, label in nav_items:
        current = ' aria-current="page"' if active_page == key else ""
        nav_links += f'<a href="{href}"{current}>{label}</a>'

    return f"""
<header class="site-header">
  <div class="site-header__brand-group">
    <a class="site-header__brand" href="/" aria-label="Носи Красиво — главная">
      <img src="/images/brand/logo-mark.png" alt="" width="68" height="68" />
      <span>Носи <em>Красиво</em></span>
    </a>
  </div>
  <h1 class="site-header__title">{safe_title}</h1>

  <nav class="site-header__nav" aria-label="Информационные страницы">
    {nav_links}
  </nav>

  <button class="site-header__profile site-header__profile-button" type="button" id="authTrigger" aria-haspopup="dialog" aria-controls="authModal">
    <span class="site-avatar" aria-hidden="true" data-auth-avatar><span class="site-icon site-icon--user-round"></span></span>
    <span data-auth-account-label>Войти</span>
  </button>

  <div id="authModal" class="auth-modal" role="dialog" aria-modal="true" aria-labelledby="authModalTitle" hidden>
    <button class="auth-modal__backdrop" type="button" aria-label="Закрыть окно входа" data-auth-close></button>

    <div class="auth-modal__content">
      <button class="auth-modal__close" type="button" aria-label="Закрыть окно входа" data-auth-close></button>

      <h2 class="auth-modal__title" id="authModalTitle">Вход в аккаунт</h2>
      <p class="auth-modal__subtitle" id="authModalSubtitle">Добро пожаловать обратно</p>

      <form id="loginForm" class="auth-form">
        <div class="auth-form__group auth-register-field" hidden>
          <label for="registerName">Имя</label>
          <input class="ui-input" type="text" id="registerName" name="name" autocomplete="name" minlength="1" maxlength="100" placeholder="Анна" disabled>
        </div>

        <div class="auth-form__group">
          <label for="loginEmail">Почта</label>
          <input class="ui-input" type="email" id="loginEmail" name="email" autocomplete="email" placeholder="you@example.com" required>
        </div>

        <div class="auth-form__group">
          <label for="loginPassword">Пароль</label>
          <input class="ui-input" type="password" id="loginPassword" name="password" autocomplete="current-password" minlength="1" maxlength="72" placeholder="Ваш пароль" required>
        </div>

        <button type="submit" class="auth-form__submit ui-button" id="authSubmit">Войти</button>
      </form>

      <div class="auth-modal__footer">
        <span id="authSwitchText">Пока нет аккаунта?</span>
        <button type="button" class="auth-switch" id="switchToRegister">Зарегистрироваться</button>
      </div>

      <div class="auth-status" id="authStatus" role="status" aria-live="polite" hidden></div>
    </div>
  </div>
</header>
"""
