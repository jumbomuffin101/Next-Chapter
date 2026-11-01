# TKH alumni theme

Colors come from the TKH brand palette, defined once in `src/index.css` and
shared by the admin and alumni dashboards. `src/tkh.css` (Chris's component styles, scoped to `.tkh-app`) maps its tokens onto them.

| Token | Value | Use |
| --- | --- | --- |
| TKH Purple (`--tkh-purple`) | `#5F3CB4` | Headings, primary buttons, selected tab, banner |
| Bright White (`--white`) | `#FFFFFF` | Page and card backgrounds |
| Dark Charcoal (`--charcoal`) | `#1A1A1A` | Body text |
| Light Lavender Tint (`--lavender`) | `#F4F0FA` | Container backgrounds, callouts, icon tiles |
| Lato (`TKH Lato`) | 400, 700, 900 | Whole app; files in `src/assets/fonts/` |

Muted text, borders, and error colors are dashboard-specific supporting colors.

Sources:
- Homepage HTML: https://www.theknowledgehouse.org/
- Typography: https://d2x0vsetbcibj0.cloudfront.net/static-final/css/base.css
- Logo: https://d2x0vsetbcibj0.cloudfront.net/media/logos/TKH_Horizontal_Purple_Logo.png
- Fonts: https://fonts.googleapis.com/css2?family=Lato:wght@400;700;900&display=swap
- Lato license: `src/assets/fonts/Lato-OFL.txt`

The logo is stored at `src/assets/tkh-logo.png` and fonts under `src/assets/fonts/`, so previewing the dashboard
does not require requests to TKH or Google Fonts.

Run `npm run dev` from `work/dashboard`, then open `/src/user/preview.html` on
the printed local URL. The preview loads the shared global stylesheet for colors and fonts.
