# Practice Room web app

V2-010 brings the V2-006 React/TypeScript workspace forward at user priority. This remains an
isolated sample experience until the later API, audio and consent integration work passes.

## Stack

- React 19, strict TypeScript and Vite, with exact dependency versions and an npm lockfile.
- Tailwind CSS 4 through `@tailwindcss/vite`; semantic CSS theme tokens, no Tailwind v3 config.
- shadcn/ui components generated with CLI 4.21.0: Button, Checkbox, Native Select, Dialog and Label.
  Components are owned source under `src/components/ui`; shared classes use `src/lib/utils.ts`.
- Lucide icons with visible control labels. Icons do not replace essential text.
- Light/Dark/System preference; system is the default. An external pre-paint script applies the
  theme before the app loads. Device theme changes are followed only in System mode. Only the
  `practice-room-theme` preference is written to local storage; storage failures are nonfatal.

Reference setup: [Tailwind Vite integration](https://tailwindcss.com/docs/installation/using-vite),
[shadcn Vite setup](https://ui.shadcn.com/docs/installation/vite),
[shadcn theme guidance](https://ui.shadcn.com/docs/dark-mode/vite).

## Local checks

Use Node 24 and run `npm ci` in `web/`, then `npm run check` for lint, formatting, strict types and
production compilation. The Python browser suite separately validates the built application.

Visual direction: preserve the restrained green-accent application layout, with legible neutral
surfaces in both themes. Each screen has one main job: setup, practice, or review. Short screen and
dialog entrances clarify transitions; voice motion communicates conversation state. Reduced-motion
preferences suppress all animation and transitions. No external fonts or image services are used.
