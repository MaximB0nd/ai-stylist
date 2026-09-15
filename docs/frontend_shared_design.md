# Shared Desktop Design

FRONT-9 implements the shared shell from the supplied Nosi Krasivo HTML mockup.
Page-specific redesigns remain separate tasks.

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
Use `.ui-button--secondary` for outlined actions and native `disabled` for
unavailable buttons. Inputs support `readonly`, `disabled`, and `aria-invalid`.
Validation messages and behavior remain the responsibility of each page.
Page CSS can own width and placement; keep control colors, borders and focus
states in the shared stylesheet.

Home rules live below `.home-page` and gallery rules below `.gallery-page`.
Generation and profile use their existing unique class prefixes. Avoid importing
one page's stylesheet from another or relying on another page's wrapper.

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
