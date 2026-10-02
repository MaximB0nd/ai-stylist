from datetime import UTC, datetime


def footer():
    return f"""
<footer class="site-footer">
  <div class="site-footer__about">
    <a class="site-footer__brand" href="/">Носи Красиво</a>
    <span>&copy; {datetime.now(UTC).year}</span>
  </div>

  <p class="site-footer__tagline">Персональный стиль для каждого дня.</p>

  <nav class="site-footer__nav" aria-label="Навигация в подвале">
    <a href="/">Главная</a>
    <a href="/generation">Генерация</a>
    <a href="/gallery">Галерея</a>
    <a href="/profile">Профиль</a>
  </nav>
</footer>
"""
