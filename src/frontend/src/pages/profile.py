from html import escape

from casp.layout import Metadata

from src.components.shared.layout.app_shell import app_shell
from src.shared.profile.demo import DEMO_PROFILE

metadata = Metadata(
    title="Профиль",
    description="Данные аккаунта Носи Красиво",
)


def page():
    name = DEMO_PROFILE["name"].strip() or "Пользователь"
    initials = "".join(part[0] for part in name.split()[:2]).upper()
    safe_name = escape(name)
    safe_email = escape(DEMO_PROFILE["email"])

    return app_shell(
        f"""
<section class="profile-page" lang="ru" aria-labelledby="profile-account-title">
  <div class="profile-intro">
    <div class="profile-avatar" role="img" aria-label="Аватар: {safe_name}">
      {escape(initials)}
    </div>
    <div class="profile-identity">
      <p class="profile-caption">Личный аккаунт</p>
      <h2 id="profile-account-title">{safe_name}</h2>
    </div>
  </div>

  <dl class="profile-fields">
    <div class="profile-field">
      <dt>Имя пользователя</dt>
      <dd>{safe_name}</dd>
    </div>
    <div class="profile-field">
      <dt>Электронная почта</dt>
      <dd>{safe_email}</dd>
    </div>
  </dl>
</section>
""",
        title="Профиль",
    )
