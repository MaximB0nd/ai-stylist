from datetime import UTC, datetime


def footer():
    return f"""
<footer class="site-footer">
  <div class="site-footer__primary">
    <div class="site-footer__about">
      <a class="site-footer__brand" href="/">Носи Красиво</a>
      <p>Персональный стиль для каждого дня.</p>
    </div>

    <nav class="site-footer__nav" aria-label="Навигация в подвале">
      <a href="/">Главная</a>
      <a href="/generation">Генерация</a>
      <a href="/gallery">Галерея</a>
      <a href="/profile">Профиль</a>
    </nav>
  </div>

  <div class="site-footer__meta">
    <span>&copy; {datetime.now(UTC).year} Носи Красиво</span>
    <span>Образы, собранные вокруг вас</span>
  </div>
</footer>
"""
