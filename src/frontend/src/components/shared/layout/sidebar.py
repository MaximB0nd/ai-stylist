def sidebar():
    return r"""
<aside class="site-sidebar" aria-label="Main navigation">
  <a class="site-sidebar__brand" href="/">
    <span class="site-sidebar__logo">S</span>
    <span class="site-sidebar__name">Носи Красиво</span>
  </a>

  <nav class="site-sidebar__nav">
    <a class="site-sidebar__link" href="/">Главная</a>
    <a class="site-sidebar__link" href="/generation">Генерация</a>
    <a class="site-sidebar__link" href="/gallery">Галерея</a>
    <a class="site-sidebar__link" href="/profile">Профиль</a>
  </nav>
</aside>
"""
