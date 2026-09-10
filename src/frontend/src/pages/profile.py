from casp.layout import Metadata

from src.components.shared.layout.app_shell import app_shell

metadata = Metadata(
    title="Профиль",
    description="Данные аккаунта Носи Красиво",
)


def page():
    return app_shell(
        """
<section class="profile-page" aria-labelledby="profile-account-title">
  <h2 id="profile-account-title">Ваш аккаунт</h2>
</section>
""",
        title="Профиль",
    )
