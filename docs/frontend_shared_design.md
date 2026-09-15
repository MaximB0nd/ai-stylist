# Shared Desktop Design

FRONT-9 implements the shared shell from the supplied Nosi Krasivo HTML mockup.
FRONT-15 applies its typography and palette to home, generation, gallery, album
and profile. Page-specific redesigns remain separate tasks.

## Foundations

`public/css/shared/tokens.css` owns the palette, fonts, spacing, radii and shell
dimensions. It loads before `base.css`. Fonts are self-hosted in `public/fonts`;
no font CDN or network connection is required at runtime.

Exactly three font families are bundled and used, with three distinct roles:
EB Garamond Regular 400 for display headings, Literata Italic 300 for rare accents,
and Manrope ExtraLight 200 for all ordinary text. Literata is used for
the brand's accent word with its near-upright cursive forms and optical sizing.
The accent uses the shared rose color token. Ordinary text has exactly two sizes:
16px for body copy and form-section titles, 14px for labels, navigation, inputs
and buttons. Both use the same 200 weight, including active navigation. Hierarchy
comes from size, spacing and color, not extra bold weights. The selected thin
weight is a design preference; keep adequate contrast and do not shrink it further.
Use the shared family, weight and size tokens instead of local variations.
Display sizes also have shared roles: `--text-hero` (60px), `--text-page`
(52px), `--text-section` (30px), `--text-card` (26px) and `--text-dialog`
(32px). Avatar initials and existing icon glyphs have independent visual sizes;
they are not additional body-text styles. Never shrink labels below 14px.

The unmodified variable TTFs come from the Google Fonts repository directories
`ofl/ebgaramond`, `ofl/literata` and `ofl/manrope`, downloaded on 2026-09-15. All include
Cyrillic and are redistributed with their SIL OFL 1.1 files alongside the fonts.
Sources: https://github.com/google/fonts/tree/main/ofl/ebgaramond,
https://github.com/google/fonts/tree/main/ofl/literata and
https://github.com/google/fonts/tree/main/ofl/manrope.

Marggraff Kursiv Zarte is not bundled: the discovered distribution only specifies
personal use. Its web embedding and redistribution permissions must be verified
before adding it. Literata is the only italic face; EB Garamond Italic is not
bundled. Generic serif/sans-serif fallbacks only apply if a font fails to load;
they do not add another downloaded font family.

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

The skip link opts out of Caspian SPA navigation with `pp-spa="false"` so the
browser moves keyboard focus to the main landmark instead of replacing the page.

The brand image is extracted from the supplied HTML mockup. Navigation icons are
vendored from https://github.com/lucide-icons/lucide under `public/icons/lucide`,
including the upstream license. No icon or font CDN is needed at runtime.

## Shared Controls and Page Ownership

`shared/controls.css` provides opt-in `.ui-button` and `.ui-input` classes.
Use `.ui-button--secondary` for outlined actions, `.ui-button--quiet` for
low-emphasis actions, and native `disabled` for unavailable buttons.
Always combine a modifier with `.ui-button`. Inputs support `readonly`,
`disabled`, and `aria-invalid`.
Validation messages and behavior remain the responsibility of each page.
Page CSS can own width and placement; keep control colors, borders and focus
states in the shared stylesheet.

Home rules live below `.home-page`, gallery rules below `.gallery-page`,
and album rules below `.album-page`, including media-query rules.
Generation and profile use their existing unique class prefixes. Avoid importing
one page's stylesheet from another or relying on another page's wrapper.

In particular, album's `.album-meta`, `.tag` and `.page-heading` must never
be global selectors. A global `.album-meta` rule changes gallery card captions.
The album uses the gallery navigation key and keeps its existing demo content.

## Palette Usage

Use `--color-canvas` for the page background and `--color-surface` for
individual items and fields. Use `--color-ink` for primary text,
`--color-muted` for secondary text, and `--color-line` for boundaries.
Primary actions and selected indicators use `--color-accent`; its hover
variant is `--color-accent-hover`. Quiet and secondary controls use
`--color-soft` on hover. `--color-overlay` is the shared translucent
backdrop for the login dialog and archived-image badges.

Do not introduce local hex colors for interface text, borders or control states.
The grayscale gradients and silhouettes in existing demo previews are temporary
media placeholders, not interface colors. Their replacement belongs to the
page-design tasks and is intentionally outside FRONT-15.
Profile values remain semantic description-list text, not editable inputs.

## Verification

Run the configured Ruff checks for changed Python files, unittest discovery in
`src/frontend/tests`, and the frontend build before committing. Shared-layout
tests cover page navigation state, title escaping, landmarks and old callers.

Browser checks for FRONT-9 covered home, generation, gallery and profile at 1280,
1440 and 1920 pixels: no horizontal overflow, active navigation, local assets,
footer placement, shared buttons and fields. Keyboard checks covered the skip
link and input focus; the existing auth dialog still closes on its backdrop.
Page-specific galleries, photo placeholders, forms and authentication remain
separate work. FRONT-8 album routes are not introduced by this change.

FRONT-15 verification covers all five pages at 1280, 1440 and 1920px:
no horizontal or text-container overflow, only the three intended font families,
and body text at 200 weight. Existing plus/arrow/close glyphs are size exceptions.
The album action hover and keyboard focus, input focus, gallery-to-album links,
album return link, browser Back, home-to-generation link, and login backdrop
close were exercised in the browser. Gallery captions stay block-level with no
album-specific margins after navigating between the two pages.

Unittest coverage includes all four demo albums, their five previews and tags,
the unknown-album fallback, shared control classes and album's active navigation.
The local checks are `python -m ruff check src/pages/album.py tests`,
`python -m unittest discover -s tests -v`, and `npm run build`, run from
`src/frontend` with the project's virtual environment active.
No CSS linter or separate type-check script is configured; no new tool is added.
