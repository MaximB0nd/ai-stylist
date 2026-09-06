from casp.component_decorator import html


def layout():
    return html(r"""
<!DOCTYPE html>
<html lang="en">
  <head>
    {% set page_title = metadata.title if metadata is defined else "AI Stylist" %}
    {% set page_description = metadata.description if metadata is defined else "AI Stylist frontend" %}
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{{ page_title }}</title>
    <meta name="description" content="{{ page_description }}" />
    <link href="/css/index.css" rel="stylesheet" />
    <script type="module" src="/js/main.js"></script>
  </head>
  <body>
    <slot />
  </body>
</html>
""")
