# FORGE documentation

The FORGE user guide, built with [Astro Starlight](https://starlight.astro.build/).

## Edit

Pages are Markdown files in `src/content/docs/`; the folder path is the page's URL. Images live in `src/assets/`. The sidebar order is set in `astro.config.mjs`. When you add a page, add it to the sidebar there too.

Use Starlight asides for callouts:

```md
:::caution
Something the reader must not miss.
:::
```

## Run locally

Requires Node.js 18.20.8 or later.

```
cd docs-site
npm install
npm run dev        # live preview at http://localhost:4321
npm run build      # static site in dist/
npm run preview    # serve the built site
```
