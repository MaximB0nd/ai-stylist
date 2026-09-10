from casp.layout import Metadata

from src.components.shared.layout.app_shell import app_shell

metadata = Metadata(
    title="Носи Красиво",
    description="AI stylist frontend",
)


def page():
    return app_shell(
        r"""
<section class="home-page" aria-labelledby="page-title">
  <div class="content-wrapper">
    <div class="greeting">
      <button class="home-avatar" id="avatarButton" type="button" onclick="document.getElementById('authModal').style.display='flex'">
        A
      </button>
      <div class="greeting-text">Добрый день, Анна</div>
    </div>

    <div id="authModal" class="modal">
      <button class="modal-backdrop" type="button" aria-label="Закрыть окно входа" onclick="document.getElementById('authModal').style.display='none'"></button>

      <div class="modal-content">
        <button class="close" id="closeModal" type="button" onclick="document.getElementById('authModal').style.display='none'">
          &times;
        </button>

        <h2 class="modal-title">Вход в аккаунт</h2>
        <p class="modal-subtitle">Добро пожаловать обратно</p>

        <form id="loginForm" class="auth-form">
          <div class="form-group">
            <label for="loginEmail">Почта</label>
            <input type="email" id="loginEmail" placeholder="you@example.com" required>
          </div>

          <div class="form-group">
            <label for="loginPassword">Пароль</label>
            <input type="password" id="loginPassword" placeholder="Ваш пароль" required>
          </div>

          <button type="submit" class="btn-submit">Войти →</button>
        </form>

        <div class="form-footer">
          Пока нет аккаунта? <a href="#" id="switchToRegister">Зарегистрироваться</a>
        </div>

        <div class="demo-hint">
          <strong>Демовход:</strong> любая почта и пароль от 8 символов.<br>
          Данные не отправляются.
        </div>
      </div>
    </div>

    <section class="hero">
      <div class="hero-content">
        <h2 class="hero-title" id="page-title">
          <span>Создайте</span>
          <span>новые образы <span class="sparkle">✧</span></span>
        </h2>
        <p class="hero-description">Ответьте на 4 вопроса — мы соберём новый альбом</p>
        <a class="generate-button" href="/generation">Генерировать</a>
      </div>

      <div class="hero-images" aria-label="Примеры образов">
        <div class="fashion-image image-main"></div>
        <div class="fashion-image image-top"></div>
        <div class="fashion-image image-bottom"></div>
      </div>
    </section>

    <section class="albums-section">
      <h2 class="section-title">Последние альбомы</h2>

      <div class="albums-grid">
        <article class="album-card">
          <div class="album-image office"></div>
          <div class="album-info">
            <div class="album-name">Офис</div>
            <div class="album-date">2 сентября</div>
          </div>
        </article>

        <article class="album-card">
          <div class="album-image evening"></div>
          <div class="album-info">
            <div class="album-name">Вечер</div>
            <div class="album-date">31 августа</div>
          </div>
        </article>
      </div>

      <div class="all-albums">
        <span class="all-albums-link all-albums-link--disabled" aria-disabled="true">
          Все альбомы <span>→</span>
        </span>
      </div>
    </section>
  </div>
</section>
""",
        title="Главная",
    )
