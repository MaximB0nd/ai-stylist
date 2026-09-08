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
  <div class="app-card">
    <p class="app-name">Носи Красиво</p>
    <h2 id="page-title" class="home-page__title">Frontend is ready</h2>
    <p class="app-description">
      Minimal Caspian project is running.
    </p>
  </div>
</section>
""",
        title="Главная",
    )
