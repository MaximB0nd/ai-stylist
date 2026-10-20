import { readSession } from "./auth.js?v=front22-1";
import { previewAlbums } from "./album-preview.js?v=front22-2";

const API_BASE = globalThis.AI_STYLIST_API_BASE ?? "/api/v1";
async function request(path, token, signal) {
  const response = await fetch(`${API_BASE}${path}`, {
    signal,
    headers: { Accept: "application/json", Authorization: `Bearer ${token}` },
  });
  if (response.status === 401) throw new Error("Сессия завершилась. Войдите снова.");
  if (!response.ok) throw new Error("Не удалось загрузить альбомы. Попробуйте ещё раз.");
  return response.json();
}

function albumCard(album) {
  const link = document.createElement("a");
  link.className = "album-card";
  link.href = `/album/${encodeURIComponent(album.id)}`;
  const preview = document.createElement("div");
  preview.className = "album-preview";
  const photo = [...(album.photos || [])].sort((a, b) => a.order_index - b.order_index)[0];
  if (photo?.url) {
    const image = document.createElement("img");
    image.className = "album-image";
    image.src = photo.url;
    image.alt = "";
    image.loading = "lazy";
    preview.append(image);
  } else {
    preview.textContent = "Образы готовятся";
    preview.classList.add("album-preview--empty");
  }
  const footer = document.createElement("div");
  footer.className = "album-footer";
  const meta = document.createElement("div");
  meta.className = "album-meta";
  const heading = document.createElement("h3");
  heading.className = "album-name";
  heading.textContent = album.title || "Ваш альбом";
  const date = document.createElement("time");
  date.className = "album-date";
  date.dateTime = album.created_at || "";
  const parsed = new Date(album.created_at);
  date.textContent = Number.isNaN(parsed.getTime()) ? "" : new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long", year: "numeric" }).format(parsed);
  const arrow = document.createElement("span");
  arrow.className = "album-arrow";
  arrow.setAttribute("aria-hidden", "true");
  arrow.textContent = "↗";
  meta.append(heading, date);
  footer.append(meta, arrow);
  link.append(preview, footer);
  return link;
}

function mountGallery(page) {
  const events = new AbortController();
  const message = page.querySelector("[data-gallery-message]");
  const grid = page.querySelector("[data-gallery-grid]");
  const session = readSession();
  if (!session) {
    if (page.dataset.previewEnabled === "true") {
      grid.replaceChildren(...previewAlbums.map(albumCard));
      message.textContent = "";
    } else {
      message.textContent = "Войдите в аккаунт, чтобы увидеть свои альбомы.";
    }
    return () => events.abort();
  }
  (async () => {
    try {
      const listing = await request("/albums", session.access_token, events.signal);
      const results = await Promise.allSettled((listing.album_ids || []).map(
        (id) => request(`/albums/${encodeURIComponent(id)}`, session.access_token, events.signal),
      ));
      if (events.signal.aborted) return;
      const albums = results.filter((result) => result.status === "fulfilled").map((result) => result.value);
      const failed = results.length - albums.length;
      albums.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
      grid.replaceChildren(...albums.map(albumCard));
      message.textContent = failed
        ? "Некоторые альбомы не удалось загрузить. Обновите страницу."
        : albums.length ? "" : "Пока нет созданных альбомов.";
    } catch (error) {
      if (!events.signal.aborted) message.textContent = error.message;
    }
  })();
  return () => events.abort();
}

let currentPage;
let release;

export function initializeGallery() {
  const page = document.querySelector(".gallery-page");
  if (page === currentPage) return;
  release?.();
  currentPage = page;
  release = page ? mountGallery(page) : undefined;
}

export function releaseGallery() {
  release?.();
  release = undefined;
  currentPage = undefined;
}
