from datetime import UTC, datetime


def footer():
    return f"""
<footer class="site-footer">
  <a class="site-footer__brand" href="/">
    <img src="/images/brand/logo-mark.png" alt="" width="38" height="38" />
    <span>Носи Красиво</span>
    <span class="site-footer__copyright">&copy; {datetime.now(UTC).year}</span>
  </a>
</footer>
"""
