# Frontend generation integration

The frontend uses the backend API rather than creating preview albums locally.
Set `AI_STYLIST_API_BASE` to the browser-accessible API prefix. It defaults to
`/api/v1` for deployments with a same-origin proxy; a direct local backend can
use `http://127.0.0.1:8000/api/v1` if its CORS configuration allows the frontend
origin. The frontend does not start PostgreSQL, object storage, or AI Core.

An authenticated submission sends `multipart/form-data` to `POST /generations`.
The form retains the validated `File` objects after clearing the visible file
inputs so replacement and drag-and-drop behave consistently. Its `occasion`,
`style`, `shoe`, and `mood` values map to `situation`, `styles`, `shoes`, and
`impressions`; gender maps to `f` or `m`. The browser shows the launch notice
only after the backend accepts the job and returns a `generation_id`.

The current tab stores accepted generation IDs in `sessionStorage`, scoped to
the authenticated user ID. The gallery polls `GET /generations/{id}/status`
every five seconds, displays an animated pending card for active jobs, and
reloads completed albums from `GET /albums`. A failed job shows a dismissible
error card. The pending card cannot follow the user to a different device
because the existing album-list endpoint returns only completed albums; a
backend list of active jobs is required for cross-device status continuity.

No development account or sample album is served by the frontend. Real end-to-end
generation requires a running backend, storage, and AI Core. The privacy page
remains an unapproved draft and must be completed with actual operator details,
retention, and contacts before public use.
