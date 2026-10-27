import { readSession } from "./auth.js";

export async function apiRequest(path, options = {}) {
  const session = readSession();
  const headers = { Accept: "application/json", ...options.headers };
  if (session) headers.Authorization = `Bearer ${session.access_token}`;
  if (typeof options.body === "string") headers["Content-Type"] = "application/json";
  let response;
  try {
    response = await fetch(`${globalThis.AI_STYLIST_API_BASE ?? "/api/v1"}${path}`, { ...options, headers });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new Error("Нет соединения с сервером. Проверьте подключение и повторите попытку.");
  }
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401 && readSession()?.access_token === session?.access_token) {
      localStorage.removeItem("aiStylistAuth");
      window.dispatchEvent(new CustomEvent("ai-stylist-auth:changed", { detail: { session: null } }));
    }
    const message = response.status === 401 ? "Войдите в аккаунт, чтобы продолжить."
      : typeof payload?.detail === "string" ? payload.detail
      : Array.isArray(payload?.detail) ? payload.detail.map(item => item.msg).join("; ")
      : `Ошибка сервера (${response.status}). Попробуйте позже.`;
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return payload;
}

export function requireSession() {
  if (!readSession()) {
    document.getElementById("authTrigger")?.click();
    throw new Error("Войдите в аккаунт, чтобы продолжить.");
  }
}

export function generationPayload(form, photos) {
  const source = form instanceof FormData ? form : new FormData(form);
  const body = new FormData();
  for (const name of ["age", "height", "gender"]) body.set(name, source.get(name));
  for (const [field, input] of Object.entries({ situation: "occasion", styles: "style", shoes: "shoe", impressions: "mood" })) {
    body.set(field, source.get(input));
  }
  body.set("gender", { female: "f", male: "m" }[source.get("gender")] ?? source.get("gender"));
  for (const photo of photos) body.set(`${photo.input.name}_photo`, photo.file);
  return body;
}
