import { readSession } from "./auth.js?v=front31-1";

const API_BASE = globalThis.AI_STYLIST_API_BASE ?? "/api/v1";
const ALBUM_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const CHOICES = {
  occasion: { street: "Улица", study: "Учёба", office: "Офис", evening: "Вечер" },
  style: { minimal: "Базовый", minimalism: "Базовый", classic: "Классика", casual: "Свободный", romantic: "Романтика" },
  shoe: { sneakers: "Кроссовки", loafers: "Лоферы", heels: "Каблук", boots: "Ботинки" },
  mood: { confident: "Уверенное", elegant: "Элегантное", relaxed: "Уютное", bright: "Яркое" },
};

export function albumChoice(key, value) {
  const label = CHOICES[key]?.[value];
  if (!label) return { label: value || "Нет данных", image: null };
  const imageValue = value === "minimalism" ? "minimal" : value;
  return { label, image: `/images/generation/${key}-${imageValue}.webp?v=3` };
}

function first(value) {
  return Array.isArray(value) ? value[0] : value;
}

async function getAlbum(albumId, signal) {
  const session = readSession();
  if (!session) throw new Error("Войдите в аккаунт, чтобы посмотреть данные альбома.");
  const response = await fetch(`${API_BASE}/albums/${encodeURIComponent(albumId)}`, {
    signal,
    headers: { Accept: "application/json", Authorization: `Bearer ${session.access_token}` },
  });
  if (response.status === 401) throw new Error("Сессия завершилась. Войдите снова.");
  if (response.status === 403 || response.status === 404) throw new Error("Альбом не найден или у вас нет доступа к нему.");
  if (!response.ok) throw new Error("Не удалось загрузить данные альбома. Попробуйте ещё раз.");
  return response.json();
}

function setPhoto(container, url) {
  const image = container.querySelector("img");
  const empty = container.querySelector("span");
  image.hidden = true;
  empty.hidden = false;
  image.removeAttribute("src");
  if (!url) return;
  image.onload = () => { image.hidden = false; empty.hidden = true; };
  image.onerror = () => { image.hidden = true; empty.hidden = false; };
  image.src = url;
}

function renderDetails(dialog, album) {
  const values = {
    occasion: album.situation,
    style: first(album.styles),
    shoe: first(album.shoes),
    mood: first(album.impressions),
  };
  for (const [key, value] of Object.entries(values)) {
    const card = dialog.querySelector(`[data-album-choice="${key}"]`);
    const { label, image } = albumChoice(key, value);
    card.querySelector("[data-album-choice-label]").textContent = label;
    const illustration = card.querySelector("img");
    illustration.hidden = !image;
    if (image) illustration.src = image;
    else illustration.removeAttribute("src");
  }
  dialog.querySelector('[data-album-fact="age"]').textContent = album.user_age == null ? "Нет данных" : `${album.user_age} лет`;
  dialog.querySelector('[data-album-fact="height"]').textContent = album.user_height == null ? "Нет данных" : `${album.user_height} см`;
  dialog.querySelector('[data-album-fact="gender"]').textContent = { f: "Женский", m: "Мужской", female: "Женский", male: "Мужской" }[album.gender] ?? "Нет данных";
  setPhoto(dialog.querySelector('[data-album-photo="face"]'), album.source_face_url);
  setPhoto(dialog.querySelector('[data-album-photo="body"]'), album.source_body_url);
  dialog.querySelector("[data-album-details-status]").textContent = "";
  dialog.querySelector("[data-album-details-content]").hidden = false;
}

function renderAlbum(page, album) {
  page.querySelector("#album-title").textContent = album.title || "Ваш альбом";
  const date = new Date(album.created_at);
  page.querySelector("[data-album-date]").textContent = Number.isNaN(date.getTime()) ? "" : new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric" }).format(date);
  const photos = [...(album.photos || [])].sort((a, b) => a.order_index - b.order_index);
  const grid = page.querySelector("[data-looks-grid]");
  grid.replaceChildren();
  for (const [index, photo] of photos.entries()) {
    const button = document.createElement("button");
    button.className = "look-card";
    button.type = "button";
    button.dataset.lookIndex = String(index);
    button.setAttribute("aria-label", `Открыть образ ${index + 1}`);
    const visual = document.createElement("div");
    visual.className = "look-visual";
    const image = document.createElement("img");
    image.src = photo.url;
    image.alt = `Образ ${index + 1}`;
    image.loading = "lazy";
    visual.append(image);
    button.append(visual);
    grid.append(button);
  }
  const status = page.querySelector("[data-album-looks-status]");
  status.textContent = photos.length ? "" : "В этом альбоме пока нет готовых образов.";
}

function mountAlbum(page) {
  const events = new AbortController();
  const dialog = document.querySelector("[data-album-details]");
  const trigger = page.querySelector("[data-album-details-trigger]");
  const lightbox = document.querySelector("[data-lightbox]");
  const albumId = page.dataset.albumId;
  let activeCard = null;
  let current = 0;
  let closeTimer;
  let positionFrame;
  const heading = page.querySelector(".album-heading");
  const syncTriggerRight = () => {
    const viewportGap = window.matchMedia("(max-width: 640px)").matches ? 16 : 24;
    const right = heading.getBoundingClientRect().right - window.innerWidth + viewportGap;
    trigger.style.setProperty("--album-trigger-right", `${right}px`);
  };
  const trackSidebarTransition = () => {
    window.cancelAnimationFrame(positionFrame);
    const started = performance.now();
    const update = () => {
      syncTriggerRight();
      if (performance.now() - started < 300) positionFrame = window.requestAnimationFrame(update);
    };
    positionFrame = window.requestAnimationFrame(update);
  };
  syncTriggerRight();
  positionFrame = window.requestAnimationFrame(syncTriggerRight);
  const geometryObserver = new ResizeObserver(syncTriggerRight);
  geometryObserver.observe(heading);
  geometryObserver.observe(document.querySelector(".site-main"));
  const positionDetails = () => {
    const top = Math.max(88, trigger.getBoundingClientRect().top - 13);
    dialog.style.setProperty("--album-details-top", `${top}px`);
  };
  const closeDetails = () => {
    if (dialog.hidden || dialog.dataset.closing === "true") return;
    trigger.setAttribute("aria-expanded", "false");
    trigger.focus();
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      dialog.hidden = true;
      return;
    }
    dialog.dataset.closing = "true";
    closeTimer = window.setTimeout(() => {
      dialog.hidden = true;
      delete dialog.dataset.closing;
    }, 220);
  };

  const cards = () => [...page.querySelectorAll(".look-card")];
  const showLook = (index) => {
    const items = cards();
    if (!items.length) return;
    current = (index + items.length) % items.length;
    activeCard = items[current];
    const source = activeCard.querySelector("img");
    lightbox.querySelector("[data-lightbox-image]").src = source.src;
    lightbox.querySelector("[data-lightbox-image]").alt = source.alt;
    lightbox.querySelector("[data-lightbox-caption]").textContent = `Образ ${current + 1} из ${items.length}`;
    lightbox.hidden = false;
    document.body.classList.add("lightbox-open");
    lightbox.querySelector("[data-lightbox-close]").focus();
  };
  const closeLook = () => {
    lightbox.hidden = true;
    document.body.classList.remove("lightbox-open");
    activeCard?.focus();
  };

  page.addEventListener("click", (event) => {
    const card = event.target.closest(".look-card");
    if (card && page.contains(card)) showLook(cards().indexOf(card));
  }, { signal: events.signal });
  lightbox.querySelector("[data-lightbox-close]").addEventListener("click", closeLook, { signal: events.signal });
  lightbox.querySelector("[data-lightbox-prev]").addEventListener("click", () => showLook(current - 1), { signal: events.signal });
  lightbox.querySelector("[data-lightbox-next]").addEventListener("click", () => showLook(current + 1), { signal: events.signal });
  lightbox.addEventListener("click", (event) => { if (event.target === lightbox) closeLook(); }, { signal: events.signal });
  document.addEventListener("keydown", (event) => {
    if (lightbox.hidden) return;
    if (event.key === "Escape") closeLook();
    if (event.key === "ArrowLeft") showLook(current - 1);
    if (event.key === "ArrowRight") showLook(current + 1);
  }, { signal: events.signal });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !dialog.hidden) closeDetails();
  }, { signal: events.signal });
  document.addEventListener("click", (event) => { if (event.target.closest("[data-sidebar-toggle]")) trackSidebarTransition(); }, { signal: events.signal });
  window.addEventListener("resize", () => { syncTriggerRight(); if (!dialog.hidden) positionDetails(); }, { signal: events.signal });

  trigger.addEventListener("click", async () => {
    window.clearTimeout(closeTimer);
    delete dialog.dataset.closing;
    positionDetails();
    dialog.hidden = false;
    trigger.setAttribute("aria-expanded", "true");
    dialog.querySelector("[data-album-details-close]").focus();
    dialog.querySelector("[data-album-details-content]").hidden = false;
    const status = dialog.querySelector("[data-album-details-status]");
    if (!ALBUM_ID.test(albumId)) {
      status.textContent = "Альбом не найден.";
      return;
    }
    status.textContent = "Загрузка данных подбора…";
    try {
      const album = await getAlbum(albumId, events.signal);
      if (events.signal.aborted) return;
      renderAlbum(page, album);
      renderDetails(dialog, album);
    } catch (error) {
      if (!events.signal.aborted) status.textContent = error.message;
    }
  }, { signal: events.signal });
  dialog.querySelector("[data-album-details-close]").addEventListener("click", closeDetails, { signal: events.signal });

  if (ALBUM_ID.test(albumId)) {
    getAlbum(albumId, events.signal).then((album) => renderAlbum(page, album)).catch((error) => {
      if (!events.signal.aborted) page.querySelector("[data-album-looks-status]").textContent = error.message;
    });
  } else {
    page.querySelector("[data-album-looks-status]").textContent = "Альбом не найден.";
  }
  return () => {
    events.abort();
    geometryObserver.disconnect();
    window.cancelAnimationFrame(positionFrame);
    window.clearTimeout(closeTimer);
    delete dialog.dataset.closing;
    dialog.hidden = true;
    document.body.classList.remove("lightbox-open");
  };
}

let currentPage;
let release;

export function initializeAlbum() {
  const page = document.querySelector(".album-page");
  if (page === currentPage) return;
  release?.();
  currentPage = page;
  release = page ? mountAlbum(page) : undefined;
}

export function releaseAlbum() {
  release?.();
  release = undefined;
  currentPage = undefined;
}
