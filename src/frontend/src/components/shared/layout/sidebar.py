def sidebar(active_page=None):
    items = (
        ("home", "/", "Главная", "house"),
        ("generation", "/generation", "Подобрать образ", "sparkles"),
        ("gallery", "/gallery", "Галерея", "images"),
    )
    links = []
    for key, path, label, icon in items:
        current = ' aria-current="page"' if key == active_page else ""
        links.append(
            f'<a class="site-sidebar__link" href="{path}" aria-label="{label}"{current}>'
            f'<span class="site-icon site-icon--{icon}" aria-hidden="true"></span>'
            f"<span>{label}</span></a>"
        )
    profile_current = ' aria-current="page"' if active_page == "profile" else ""
    return f"""
<aside class="site-sidebar" aria-label="Навигация по сайту">
  <button class="site-sidebar__menu" type="button" aria-expanded="true" aria-label="Свернуть меню" data-sidebar-toggle>
    <span class="site-sidebar__menu-mark" aria-hidden="true"><span></span><span></span><span></span></span>
  </button>
  <nav class="site-sidebar__nav" aria-label="Основные страницы">
    {"".join(links)}
  </nav>
  <div class="site-sidebar__bottom">
    <a class="site-sidebar__account" href="/profile" aria-label="Аккаунт"{profile_current}>
      <span class="site-avatar" aria-hidden="true" data-auth-avatar><span class="site-icon site-icon--user-round"></span></span>
      <span class="site-sidebar__account-copy" data-auth-sidebar-label>Аккаунт</span>
      <span class="site-icon site-icon--chevron-right" aria-hidden="true"></span>
    </a>
  </div>
</aside>
"""
