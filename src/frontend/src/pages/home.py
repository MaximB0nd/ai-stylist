from casp.component_decorator import html
from casp.layout import Metadata


metadata = Metadata(
    title="AI Stylist",
    description="AI Stylist frontend",
)


def page():
    return html(r"""
<main class="app-shell">
  <section class="app-card" aria-labelledby="page-title">
    <p class="app-name">AI Stylist</p>
    <h1 id="page-title">Frontend is ready</h1>
    <p class="app-description">
      Minimal Caspian project is running.
    </p>
  </section>
</main>
""")
