import { readSession } from "./auth.js";

const API_BASE = globalThis.AI_STYLIST_API_BASE ?? "/api/v1";
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
let albumEvents;

async function request(path) {
  const session = readSession();
  if (!session) return null;
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { Accept: "application/json", Authorization: `Bearer ${session.access_token}` },
  });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`Album request failed: ${response.status}`);
  return response.json();
}

function formatDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : new Intl.DateTimeFormat("ru-RU", {
    day: "numeric", month: "long", year: "numeric",
  }).format(date);
}

function image(url, className, alt = "") {
  const element = document.createElement("img");
  element.src = url;
  element.alt = alt;
  element.className = className;
  element.loading = "lazy";
  element.decoding = "async";
  element.width = 640;
  element.height = 960;
  return element;
}

function galleryCard(album, index) {
  const link = document.createElement("a");
  link.href = `/album/${album.id}`;
  link.className = "album-card";
  const preview = document.createElement("div");
  preview.className = "album-preview";
  const mosaic = document.createElement("div");
  mosaic.className = `album-mosaic album-mosaic--${index % 2 ? "right" : "left"}`;
  const photos = [...album.photos].sort((left, right) => left.order_index - right.order_index);
  if (photos[0]) mosaic.append(image(photos[0].url, "album-image album-mosaic__primary", album.title));
  if (photos[1]) mosaic.append(image(photos[1].url, "album-image album-mosaic__secondary album-mosaic__secondary--one"));
  if (photos[2]) mosaic.append(image(photos[2].url, "album-image album-mosaic__secondary album-mosaic__secondary--two"));
  preview.append(mosaic);

  const footer = document.createElement("div");
  footer.className = "album-footer";
  const metadata = document.createElement("div");
  metadata.className = "album-meta";
  const title = document.createElement("h3");
  title.className = "album-name";
  title.textContent = album.title;
  const date = document.createElement("time");
  date.className = "album-date";
  date.dateTime = album.created_at;
  date.textContent = formatDate(album.created_at);
  metadata.append(title, date);
  const arrow = document.createElement("span");
  arrow.className = "album-arrow";
  arrow.ariaHidden = "true";
  arrow.textContent = "↗";
  footer.append(metadata, arrow);
  link.append(preview, footer);
  return link;
}

async function initializeGallery() {
  const page = document.querySelector(".gallery-page[data-live-gallery]");
  if (!page || page.dataset.liveReady === "true" || !readSession()) return;
  page.dataset.liveReady = "true";
  try {
    const listing = await request("/albums");
    if (!listing) return;
    const albums = (await Promise.all(listing.album_ids.map((id) => request(`/albums/${id}`))))
      .filter(Boolean);
    const grid = page.querySelector(".albums-grid");
    grid.replaceChildren(...albums.map(galleryCard));
    page.querySelector(".gallery-count").textContent = `${albums.length} альбомов`;
  } catch {
    page.querySelector(".gallery-count").textContent = "Не удалось обновить галерею";
  }
}

function lookCard(photo, index) {
  const button = document.createElement("button");
  button.className = "look-card";
  button.type = "button";
  button.dataset.lookIndex = String(index);
  button.ariaLabel = `Открыть образ ${index + 1}`;
  const visual = document.createElement("div");
  visual.className = "look-visual";
  visual.append(image(photo.url, "", `Образ ${index + 1}`));
  const number = document.createElement("span");
  number.className = "look-number";
  number.textContent = String(index + 1).padStart(2, "0");
  visual.append(number);
  button.append(visual);
  return button;
}

function bindLightbox(page) {
  const box = document.querySelector("[data-lightbox]");
  if (!box || page.dataset.lightboxReady === "true") return;
  page.dataset.lightboxReady = "true";
  albumEvents?.abort();
  albumEvents = new AbortController();
  const options = { signal: albumEvents.signal };
  const output = box.querySelector("[data-lightbox-image]");
  const caption = box.querySelector("[data-lightbox-caption]");
  const show = (index) => {
    const cards = [...page.querySelectorAll(".look-card")];
    if (!cards.length) return;
    const current = (index + cards.length) % cards.length;
    const source = cards[current].querySelector("img");
    output.src = source.src;
    output.alt = source.alt;
    caption.textContent = `Образ ${current + 1} из ${cards.length}`;
    box.hidden = false;
    box.dataset.current = String(current);
    document.body.classList.add("lightbox-open");
  };
  page.addEventListener("click", (event) => {
    const card = event.target.closest(".look-card");
    if (!card || !page.contains(card)) return;
    show([...page.querySelectorAll(".look-card")].indexOf(card));
  }, options);
  box.querySelector("[data-lightbox-close]").addEventListener("click", () => {
    box.hidden = true;
    document.body.classList.remove("lightbox-open");
  }, options);
  box.querySelector("[data-lightbox-prev]").addEventListener("click", () => show(Number(box.dataset.current || 0) - 1), options);
  box.querySelector("[data-lightbox-next]").addEventListener("click", () => show(Number(box.dataset.current || 0) + 1), options);
  box.addEventListener("click", (event) => {
    if (event.target === box) box.querySelector("[data-lightbox-close]").click();
  }, options);
  document.addEventListener("keydown", (event) => {
    if (box.hidden) return;
    if (event.key === "Escape") box.querySelector("[data-lightbox-close]").click();
    if (event.key === "ArrowLeft") show(Number(box.dataset.current || 0) - 1);
    if (event.key === "ArrowRight") show(Number(box.dataset.current || 0) + 1);
  }, options);
}

async function initializeAlbum() {
  const page = document.querySelector(".album-page[data-album-id]");
  if (!page) {
    albumEvents?.abort();
    albumEvents = undefined;
    return;
  }
  bindLightbox(page);
  if (page.dataset.liveReady === "true" || !readSession() || !UUID.test(page.dataset.albumId)) return;
  page.dataset.liveReady = "true";
  const status = page.querySelector("[data-album-status]");
  try {
    const album = await request(`/albums/${page.dataset.albumId}`);
    if (!album) throw new Error("Album is unavailable");
    const photos = [...album.photos].sort((left, right) => left.order_index - right.order_index);
    page.querySelector("#album-title").textContent = album.title;
    page.querySelector("[data-album-date]").textContent = formatDate(album.created_at);
    page.querySelector("[data-album-count]").textContent = `${photos.length} образов`;
    page.querySelector("[data-album-looks]").replaceChildren(...photos.map(lookCard));
    document.querySelector("[data-lightbox] figcaption strong").textContent = album.title;
    status.hidden = true;
  } catch {
    status.textContent = "Не удалось загрузить альбом. Обновите страницу позже.";
    status.hidden = false;
  }
}

export function initializeAlbums() {
  void initializeGallery();
  void initializeAlbum();
}

export function handleAlbumSessionChange(event) {
  if (!event.detail?.session && document.querySelector('[data-live-ready="true"]')) {
    window.location.reload();
    return;
  }
  initializeAlbums();
}
