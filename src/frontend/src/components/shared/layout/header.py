def header(title="Носи Красиво"):
    return f"""
<header class="site-header">
  <div>
    <p class="site-header__eyebrow">Носи Красиво</p>
    <h1 class="site-header__title">{title}</h1>
  </div>

  <div class="site-header__profile" aria-label="User profile">
    <span class="site-header__avatar">A</span>
  </div>
</header>
"""
