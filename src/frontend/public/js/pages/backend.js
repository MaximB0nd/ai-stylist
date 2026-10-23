import { apiRequest, requireSession } from "./api.js";
import { readSession } from "./auth.js";

let dispose;
let activeToken;

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

export function safePhotoUrl(value) {
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : "";
  } catch { return ""; }
}

export async function fetchAlbums(signal, limit) {
  const index = await apiRequest("/albums", { signal });
  const ids = index.album_ids.slice(0, limit);
  const albums = new Array(ids.length);
  let next = 0;
  // Limit detail requests; gallery size must not flood the backend or MinIO.
  await Promise.all(Array.from({ length: Math.min(4, ids.length) }, async () => {
    while (next < ids.length) {
      const i = next++;
      try { albums[i] = await apiRequest(`/albums/${encodeURIComponent(ids[i])}`, { signal }); }
      catch (error) {
        if (error.name === "AbortError" || error.status !== 404) throw error;
      }
    }
  }));
  return albums.filter(Boolean);
}

function date(value) {
  return new Date(value).toLocaleDateString("ru-RU", { year: "numeric", month: "long", day: "numeric" });
}

function card(album, home = false) {
  const link = element("a", "album-card");
  link.href = `/album/${encodeURIComponent(album.id)}`;
  const preview = element("div", home ? "album-cover" : "album-preview");
  const mosaic = element("div", "album-mosaic album-mosaic--left");
  for (const [index, photo] of album.photos.slice(0, 3).entries()) {
    const image = element("img", `album-image ${index === 0 ? "album-mosaic__primary" : `album-mosaic__secondary album-mosaic__secondary--${index === 1 ? "one" : "two"}`}`);
    image.src = safePhotoUrl(photo.url);
    image.alt = index === 0 ? album.title : "";
    image.loading = "lazy";
    mosaic.append(image);
  }
  preview.append(mosaic);
  const footer = element("div", home ? "album-info" : "album-footer");
  const meta = element("div", "album-meta");
  meta.append(element("h3", "album-name", album.title), element("time", "album-date", date(album.created_at)));
  footer.append(meta);
  link.append(preview, footer);
  return link;
}

async function loadAlbums(container, signal, home = false) {
  const grid = container.querySelector(".albums-grid");
  const status = container.querySelector("[data-albums-status]");
  grid.replaceChildren();
  if (!readSession()) {
    status.textContent = "Войдите в аккаунт, чтобы увидеть свои альбомы.";
    return;
  }
  status.textContent = "Загружаем альбомы…";
  try {
    const albums = await fetchAlbums(signal, home ? 3 : undefined);
    if (signal.aborted) return;
    grid.replaceChildren(...albums.map(album => card(album, home)));
    status.textContent = albums.length ? "" : "Пока нет готовых альбомов. Создайте первые образы.";
    const count = container.querySelector(".gallery-count");
    if (count) count.textContent = `Альбомов: ${albums.length}`;
  } catch (error) {
    if (!signal.aborted) status.textContent = error.message;
  }
}

async function loadAlbum(page, signal) {
  const status = page.querySelector("[data-album-status]");
  const grid = page.querySelector(".looks-grid");
  const box = document.querySelector("[data-lightbox]");
  grid.replaceChildren();
  if (!readSession()) { status.textContent = "Войдите в аккаунт для просмотра альбома."; return; }
  try {
    const id = window.location.pathname.split("/").filter(Boolean).pop();
    const album = await apiRequest(`/albums/${encodeURIComponent(id)}`, { signal });
    if (signal.aborted) return;
    page.querySelector("#album-title").textContent = album.title;
    page.querySelector("time").textContent = date(album.created_at);
    page.querySelector("[data-photo-count]").textContent = `Образов: ${album.photos.length}`;
    const photos = [...album.photos].sort((a, b) => a.order_index - b.order_index);
    let current = 0;
    function show(index) {
      current = (index + photos.length) % photos.length;
      const image = box.querySelector("[data-lightbox-image]");
      image.src = safePhotoUrl(photos[current].url);
      image.alt = `Образ ${current + 1}`;
      box.querySelector("[data-lightbox-caption]").textContent = `${album.title} · ${current + 1} / ${photos.length}`;
      box.hidden = false;
      if (!box.open) box.showModal();
    }
    for (const [index, photo] of photos.entries()) {
      const button = element("button", "look-card");
      button.type = "button";
      button.setAttribute("aria-label", `Открыть образ ${index + 1}`);
      const visual = element("div", "look-visual");
      const image = element("img");
      image.src = safePhotoUrl(photo.url);
      image.alt = `Образ ${index + 1}`;
      image.loading = "lazy";
      visual.append(image, element("span", "look-number", String(index + 1).padStart(2, "0")));
      button.append(visual);
      button.addEventListener("click", () => show(index), { signal });
      grid.append(button);
    }
    box.querySelector("[data-lightbox-close]").addEventListener("click", () => box.close(), { signal });
    box.addEventListener("close", () => { box.hidden = true; }, { signal });
    box.querySelector("[data-lightbox-prev]").addEventListener("click", () => show(current - 1), { signal });
    box.querySelector("[data-lightbox-next]").addEventListener("click", () => show(current + 1), { signal });
    box.addEventListener("keydown", event => {
      if (event.key === "ArrowLeft") show(current - 1);
      if (event.key === "ArrowRight") show(current + 1);
    }, { signal });
    status.textContent = photos.length ? "" : "В альбоме пока нет фотографий.";
  } catch (error) { if (!signal.aborted) status.textContent = error.message; }
}

export const GENERATION_STATUSES = {
  VALIDATING: "Задача принята. Ожидаем отправки в AI Core…",
  QUEUED: "Генерация в очереди…", PROCESSING: "ИИ создаёт два образа…",
  DOWNLOADING: "Сохраняем готовые фотографии…",
};

function pollGeneration(page, id, controller) {
  const status = page.querySelector(".generation-status");
  const button = page.querySelector(".generation-generate");
  const form = page.querySelector("#generation-form");
  form.dataset.awaitingGeneration = "true";
  button.disabled = true;
  let timer;
  let stopped = false;
  async function poll() {
    try {
      requireSession();
      const result = await apiRequest(`/generations/${encodeURIComponent(id)}/status`, { signal: controller.signal });
      if (controller.signal.aborted) return;
      if (result.status === "COMPLETED" && result.album_id) {
        stopped = true;
        window.location.assign(`/album/${encodeURIComponent(result.album_id)}`);
        return;
      }
      if (result.status === "FAILED") {
        stopped = true;
        status.textContent = result.error_message || "Генерация не удалась. Попробуйте создать новые образы.";
        status.dataset.state = "error";
        delete form.dataset.awaitingGeneration;
        button.disabled = false;
        return;
      }
      status.textContent = GENERATION_STATUSES[result.status] || "Ожидаем результат…";
    } catch (error) {
      if (controller.signal.aborted) return;
      status.textContent = error.message;
      if ([401, 403, 404, 422].includes(error.status) || !readSession()) stopped = true;
    }
    if (!stopped && !controller.signal.aborted) timer = setTimeout(poll, 3000);
  }
  controller.signal.addEventListener("abort", () => {
    clearTimeout(timer);
    delete form.dataset.awaitingGeneration;
    if (form.isConnected) button.disabled = false;
  }, { once: true });
  void poll();
}

function mountFeedback(form, controller) {
  const status = form.querySelector("[data-feedback-status]");
  const button = form.querySelector("[type=submit]");
  const user = readSession()?.user;
  if (user) {
    if (!form.elements.name.value) form.elements.name.value = user.name || "";
    if (!form.elements.email.value) form.elements.email.value = user.email || "";
  }
  let sending = false;
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (sending || !form.reportValidity()) return;
    try {
      requireSession();
      sending = true;
      button.disabled = true;
      status.textContent = "Отправляем…";
      await apiRequest("/feedback", { method: "POST", signal: controller.signal, body: JSON.stringify({
        name: form.elements.name.value.trim(), email: form.elements.email.value.trim(), comment: form.elements.message.value.trim(),
      }) });
      if (controller.signal.aborted) return;
      form.elements.message.value = "";
      status.textContent = "Спасибо! Ваш отзыв сохранён.";
    } catch (error) { if (!controller.signal.aborted) status.textContent = error.message; }
    finally { sending = false; button.disabled = false; }
  }, { signal: controller.signal });
}

export function initializeBackend() {
  dispose?.();
  const controller = new AbortController();
  const signal = controller.signal;
  activeToken = readSession()?.access_token;
  dispose = () => {
    controller.abort();
    const box = document.querySelector("[data-lightbox]");
    if (box?.open) box.close();
  };
  const gallery = document.querySelector(".gallery-page");
  const home = document.querySelector(".home-page #home-albums");
  if (gallery) void loadAlbums(gallery, signal);
  if (home) void loadAlbums(home, signal, true);
  const album = document.querySelector(".album-page");
  if (album) void loadAlbum(album, signal);
  const feedback = document.querySelector(".feedback-form");
  if (feedback) mountFeedback(feedback, controller);
  const generation = document.querySelector(".generation-page");
  const id = new URLSearchParams(window.location.search).get("generation_id");
  if (generation && id) pollGeneration(generation, id, controller);
  for (const logout of document.querySelectorAll("[data-logout]")) {
    logout.hidden = !activeToken;
    logout.addEventListener("click", () => {
      localStorage.removeItem("aiStylistAuth");
      window.dispatchEvent(new CustomEvent("ai-stylist-auth:changed", { detail: { session: null } }));
    }, { signal });
  }
}

export function releaseBackend() { dispose?.(); dispose = undefined; }

if (typeof window !== "undefined") {
  window.addEventListener("ai-stylist-auth:changed", () => {
    if (activeToken !== readSession()?.access_token) initializeBackend();
  });
  window.addEventListener("pagehide", releaseBackend);
}
