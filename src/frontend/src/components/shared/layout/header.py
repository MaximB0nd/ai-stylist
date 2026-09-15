from html import escape


def header(title="Носи Красиво"):
    safe_title = escape(str(title))

    return f"""
<header class="site-header">
  <div>
    <div class="site-header__breadcrumb">
      <a href="/">Носи Красиво</a>
      <span aria-hidden="true">/</span>
      <h1 class="site-header__title">{safe_title}</h1>
    </div>
  </div>

  <a class="site-header__profile" href="/profile" aria-label="Открыть профиль">
    <span class="site-avatar" aria-hidden="true"><span class="site-icon site-icon--user-round"></span></span>
    <span>Мой аккаунт</span>
  </a>
</header>
"""
