from casp.component_decorator import html
from json import dumps
from os import getenv


def layout():
    api_base = dumps(getenv("AI_STYLIST_API_BASE", "/api/v1").rstrip("/")).replace("<", "\\u003c")
    source = r"""
<!DOCTYPE html>
<html lang="ru">
  <head>
    {% set page_title = metadata.title if metadata is defined else "AI Stylist" %}
    {% set page_description = metadata.description if metadata is defined else "AI Stylist frontend" %}
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{{ page_title }}</title>
    <meta name="description" content="{{ page_description }}" />
    <script>globalThis.AI_STYLIST_API_BASE = __API_BASE__;</script>
    <script>
      try {
        if (localStorage.getItem("ai-stylist-sidebar-collapsed") === "true") {
          document.documentElement.classList.add("is-sidebar-collapsed");
        }
      } catch {}
    </script>
    <link href="/css/index.css?v=front31-1" rel="stylesheet" />
    <script type="module" src="/js/main.js?v=front31-1"></script>
  </head>
  <body>
    <slot />
  </body>
</html>
"""
    return html(source.replace("__API_BASE__", api_base))
