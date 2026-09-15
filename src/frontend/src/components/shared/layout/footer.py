from datetime import UTC, datetime


def footer():
    return f"""
<footer class="site-footer">
  <span>&copy; {datetime.now(UTC).year} Носи Красиво</span>
  <span>Индивидуальность</span>
</footer>
"""
