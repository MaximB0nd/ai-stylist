import { readSession } from "./auth.js?v=front31-1";
import { forgetPendingGeneration, readPendingGenerations } from "./generation-pending.js";

const API_BASE = globalThis.AI_STYLIST_API_BASE ?? "/api/v1";
async function request(path, token, signal) {
  const response = await fetch(`${API_BASE}${path}`, {
    signal,
    headers: { Accept: "application/json", Authorization: `Bearer ${token}` },
  });
  if (response.status === 401) throw new Error("Сессия завершилась. Войдите снова.");
  if (!response.ok) throw new Error("Не удалось получить данные. Попробуйте ещё раз.");
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

function pendingAlbumCard(album, generationState) {
  const card = document.createElement("article");
  card.className = `album-card album-card--pending${generationState === "FAILED" ? " album-card--failed" : ""}`;
  card.setAttribute("aria-label", generationState === "FAILED" ? "Новый альбом: ошибка генерации" : "Новый альбом: в процессе создания");
  const preview = document.createElement("div");
  preview.className = `album-preview${generationState === "FAILED" ? " album-preview--empty" : " album-preview--pending"}`;
  preview.setAttribute("aria-hidden", "true");
  const footer = document.createElement("div");
  footer.className = "album-footer";
  const heading = document.createElement("h3");
  heading.className = "album-name";
  heading.textContent = "Новый альбом";
  const state = document.createElement("p");
  state.className = "album-generation-state";
  state.textContent = generationState === "FAILED" ? "Не удалось создать" : "В процессе";
  footer.append(heading, state);
  if (generationState === "FAILED") {
    const dismiss = document.createElement("button");
    dismiss.type = "button";
    dismiss.className = "album-pending-dismiss";
    dismiss.dataset.dismissGeneration = album.id;
    dismiss.textContent = "Убрать";
    footer.append(dismiss);
  }
  card.append(preview, footer);
  return card;
}

function mountGallery(page) {
  const events = new AbortController();
  const message = page.querySelector("[data-gallery-message]");
  const grid = page.querySelector("[data-gallery-grid]");
  const session = readSession();
  let pending = readPendingGenerations(session?.user?.id);
  const statuses = new Map();
  let albums = [];
  let listError = "";
  let polling = false;
  const render = () => {
    grid.replaceChildren(...pending.map((item) => pendingAlbumCard(item, statuses.get(item.id))), ...albums.map(albumCard));
    message.textContent = listError || (pending.length || albums.length ? "" : "Пока нет созданных альбомов.");
  };
  if (!session) {
    grid.replaceChildren();
    message.textContent = "Войдите в аккаунт, чтобы увидеть свои альбомы.";
    return () => events.abort();
  }
  render();
  const loadAlbums = async () => {
    try {
      const listing = await request("/albums", session.access_token, events.signal);
      const results = await Promise.allSettled((listing.album_ids || []).map(
        (id) => request(`/albums/${encodeURIComponent(id)}`, session.access_token, events.signal),
      ));
      if (events.signal.aborted) return;
      albums = results.filter((result) => result.status === "fulfilled").map((result) => result.value);
      const failed = results.length - albums.length;
      albums.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
      listError = failed ? "Некоторые альбомы не удалось загрузить. Обновите страницу." : "";
    } catch (error) {
      if (!events.signal.aborted) listError = error.message;
    }
    if (!events.signal.aborted) render();
  };
  const pollPending = async () => {
    if (polling || !pending.length || events.signal.aborted) return;
    polling = true;
    let completed = false;
    try {
      await Promise.all(pending.filter((item) => statuses.get(item.id) !== "FAILED").map(async (item) => {
        try {
          const result = await request(`/generations/${encodeURIComponent(item.id)}/status`, session.access_token, events.signal);
          if (result.status === "COMPLETED") {
            forgetPendingGeneration(item.id, session.user.id);
            pending = pending.filter((entry) => entry.id !== item.id);
            completed = true;
          } else if (result.status === "FAILED") {
            statuses.set(item.id, "FAILED");
          }
        } catch (error) {
          if (!events.signal.aborted) listError = error.message;
        }
      }));
      if (completed) await loadAlbums();
      if (!events.signal.aborted) render();
    } finally {
      polling = false;
    }
  };
  grid.addEventListener("click", (event) => {
    const button = event.target.closest("[data-dismiss-generation]");
    if (!button) return;
    forgetPendingGeneration(button.dataset.dismissGeneration, session.user.id);
    pending = pending.filter((item) => item.id !== button.dataset.dismissGeneration);
    render();
  }, { signal: events.signal });
  void loadAlbums();
  void pollPending();
  const timer = window.setInterval(pollPending, 5000);
  return () => { window.clearInterval(timer); events.abort(); };
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
