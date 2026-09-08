from casp.component_decorator import html

from src.components.shared.layout.footer import footer
from src.components.shared.layout.header import header
from src.components.shared.layout.sidebar import sidebar


def app_shell(content, title="Носи Красиво"):
    return html(f"""
<div class="site-shell">
  {sidebar()}

  <div class="site-shell__body">
    {header(title)}

    <main class="site-main">
      {content}
    </main>

    {footer()}
  </div>
</div>
""")
