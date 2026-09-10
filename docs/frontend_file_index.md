# Frontend File Inventory

Caspian registers routes from `src/frontend/settings/files-list.json`.
This generated file is ignored by Git. After pulling a new page, an existing
inventory can omit its route and cause a 404 even though the source is present.

The frontend entry point refreshes the app and public file inventory before
importing the Caspian application. It uses the same paths and Python-cache
exclusions as `settings/files-list.ts`. Missing, invalid, or outdated inventories
are replaced atomically; an unchanged inventory is left untouched. Route parsing
and registration remain owned by Caspian.

Restart the server after pulling changes or switching branches. The refresh runs
at startup, not during requests, and does not provide hot reload. The regular
`npm run dev` workflow remains the recommended way to rebuild all metadata.

Verification from `src/frontend`:

```powershell
uv run python -m unittest discover -s tests -v
```
