def sidebar(active_page=None):
    items = (
        ("home", "/", "Главная", "house"),
        ("generation", "/generation", "Генерация", "sparkles"),
        ("gallery", "/gallery", "Галерея", "images"),
    )
    links = []
    for key, path, label, icon in items:
        current = ' aria-current="page"' if key == active_page else ""
        links.append(
            f'<a class="site-sidebar__link" href="{path}"{current}>'
            f'<span class="site-icon site-icon--{icon}" aria-hidden="true"></span>'
            f"<span>{label}</span></a>"
        )
    profile_current = ' aria-current="page"' if active_page == "profile" else ""
    return f"""
<aside class="site-sidebar" aria-label="Навигация по сайту">
  <a class="site-sidebar__brand" href="/">
    <img class="site-sidebar__logo" src="/images/brand/logo.webp" alt="" width="48" height="64" />
    <span class="site-sidebar__name">Носи <em>Красиво</em></span>
  </a>

  <nav class="site-sidebar__nav" aria-label="Основные страницы">
    {"".join(links)}
  </nav>
  <div class="site-sidebar__bottom">
    <a class="site-sidebar__account" href="/profile"{profile_current}>
      <span class="site-avatar" aria-hidden="true"><span class="site-icon site-icon--user-round"></span></span>
      <span class="site-sidebar__account-copy">Профиль<small>Мой аккаунт</small></span>
      <span class="site-icon site-icon--chevron-right" aria-hidden="true"></span>
    </a>
  </div>
</aside>
"""
