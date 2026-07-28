// Authentication is enforced by FastAPI on every protected API endpoint and by
// AuthProvider after it verifies the browser session. Proxy cannot be the source
// of truth because local development uses a different API origin.
export function proxy() {}
