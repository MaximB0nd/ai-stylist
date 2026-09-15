from casp.component_decorator import html

from src.components.shared.layout.footer import footer
from src.components.shared.layout.header import header
from src.components.shared.layout.sidebar import sidebar


def app_shell(content, title="Носи Красиво", active_page=None):
    return html(f"""
<div class="site-shell">
  <a class="site-skip-link" href="#main-content" pp-spa="false">Перейти к содержимому</a>
  {sidebar(active_page)}

  <div class="site-shell__body">
    {header(title)}

    <main class="site-main" id="main-content" tabindex="-1">
      {content}
    </main>

    {footer()}
  </div>
</div>
""")
