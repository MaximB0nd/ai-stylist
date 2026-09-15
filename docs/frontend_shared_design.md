# Shared Desktop Design

FRONT-9 implements the shared shell from the supplied Nosi Krasivo HTML mockup.
Page-specific redesigns remain separate tasks.

## Foundations

`public/css/shared/tokens.css` owns the palette, fonts, spacing, radii and shell
dimensions. It loads before `base.css`. Segoe UI and Georgia use local system
fonts, so no font CDN or network connection is required.

The mockup's darker rose is used for primary controls and focused elements to
improve text contrast. Letter spacing stays at zero. Page content remains
unframed; only controls and individual items use rounded borders.

Keep page rules scoped to their page root. Do not style shared names such as
`.album-card` globally: the home page and gallery have different compositions.
