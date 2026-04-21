# Employee portal (internal docs)

The hub page is [`index.html`](index.html). It lists people by role groups and links to each profile under [`people/`](people/).

**Page history** on every docs page follows [`documentation-style-guide.html`](../documentation-style-guide.html#page-history) (table: Date, Change, Author).

## How it fits together

1. **Profile pages** — `people/<slug>/index.html` (e.g. [`people/ivan-boyarkin/index.html`](people/ivan-boyarkin/index.html)) are normal HTML. You edit name, bio, photo, and links by hand. The `<body>` also carries **machine-readable attributes** used by tooling (see below); they are not shown as a long explanation on the page.

2. **Generated bundle** — [`docs/assets/docs-portal-data.js`](../../assets/docs-portal-data.js) is **generated**. Do not edit it. It defines `window.__DOCS_PORTAL_DATA__` with:
   - **`people`** — one entry per profile page found under `docs/internal/portal/people/*/index.html`, parsed from the profile `<body>` attributes.
   - **`maintainerPages`** — for each person id, lists doc pages under `docs/` whose `<body>` has `data-maintainer-ids` containing that id.

3. **Generator** — [`scripts/collect_docs_portal_data.py`](../../../scripts/collect_docs_portal_data.py) builds `docs-portal-data.js`. It runs as part of **`make docs-fix`**.

4. **UI script** — [`docs/assets/docs-internal-meta.js`](../../assets/docs-internal-meta.js) (loaded after `docs-portal-data.js`) renders:
   - grouped **People** lists on the portal hub;
   - **Page editors** on any doc page that has `docs-page-meta-mount` and `data-maintainer-ids` on `<body>`;
   - the **Maintained pages** list on a profile (into `#portal-maintained-mount`) from the generated data.

## Profile `<body>` attributes (for the generator)

| Attribute | Meaning |
|-----------|---------|
| `data-person-id` | Stable id (also used in `data-maintainer-ids` on doc pages). |
| `data-person-slug` | Directory name under `people/` (default: folder name). |
| `data-display-name` | Shown in portal cards and editor block. |
| `data-github` | GitHub username. |
| `data-photo` | Filename relative to the profile folder (e.g. `photo.jpg`). |
| `data-groups` | Space-separated keys (e.g. `backend pm`). |

The hub groups people by these keys. **Labels and order** for known keys live in `docs-internal-meta.js` as `PORTAL_GROUP_ORDER` and `PORTAL_GROUP_TITLES`. Unknown keys are still listed, with a generated title unless you add them there.

After changing a profile or group labels, run **`make docs-fix`** so `docs-portal-data.js` stays in sync.

## Doc pages and maintainers

On any HTML page under `docs/` (except `docs/assets/`), set on `<body>`:

```html
data-maintainer-ids="<person-id>[,<another-id>...]"
```

Use the same `data-person-id` as on the maintainer’s profile. Include [`docs-portal-data.js`](../../assets/docs-portal-data.js) and [`docs-internal-meta.js`](../../assets/docs-internal-meta.js) if you want the **Page editors** block (`#docs-page-meta-mount`).

Then run **`make docs-fix`** so that page appears under **Maintained pages** on each listed profile.

### Bulk default editor (hand-written HTML)

Most narrative pages under `docs/` already include **`data-maintainer-ids`** with a default person id, **`#docs-page-meta-mount`**, and the two portal scripts. That was applied with [`scripts/apply_default_page_editor_to_docs.py`](../../../scripts/apply_default_page_editor_to_docs.py) (skips `docs/api/` (pdoc), `docs/assets/`, and profile pages under `internal/portal/people/`). Re-run that script after changing the default id or when adding many new pages that follow the same pattern, then **`make docs-fix`**.

## Adding a new person

1. Create `docs/internal/portal/people/<slug>/index.html` (and photo, etc.).
2. Set the `data-*` attributes on `<body>` as above.
3. Run **`make docs-fix`**.
4. Optionally add a row to the internal sidebar or other nav if your site has a manual list.

## `file://` and scripts

Scripts are loaded as classic `<script src="...">` so the portal works when opening HTML from disk. The bundle is embedded in the repo so nothing needs `fetch()` to local JSON.
