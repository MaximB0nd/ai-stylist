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

## Shared Shell

Wrap page content once with `app_shell(content, title="...", active_page="gallery")`.
Supported navigation keys are `home`, `generation`, `gallery`, and `profile`.
An album page can use `gallery` to highlight its parent section. The optional
argument keeps older callers compatible. Titles are escaped; content is trusted
HTML produced by page components, not raw user input.

The shell owns the header, sidebar, footer and `main#main-content`. Page components
should not repeat these landmarks. The sidebar uses `aria-current` for the current
section; keyboard users can skip navigation. Profile links do not imply a logged-in
user or display invented account counters.

The brand image is extracted from the supplied HTML mockup. Navigation icons are
vendored from https://github.com/lucide-icons/lucide under `public/icons/lucide`,
including the upstream license. No icon or font CDN is needed at runtime.
