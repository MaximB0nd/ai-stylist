import { readSession } from "./auth.js?v=front31-1";

const API_BASE = globalThis.AI_STYLIST_API_BASE ?? "/api/v1";
const albumLayouts = ["left", "right", "left-compact"];
let albumsPage;
let albumsToken;
let stopAlbums;

async function requestAlbum(path, token, signal) {
  const response = await fetch(`${API_BASE}${path}`, {
    signal,
    headers: { Accept: "application/json", Authorization: `Bearer ${token}` },
  });
  if (response.status === 401) throw new Error("Сессия завершилась. Войдите снова.");
  if (!response.ok) throw new Error("Не удалось загрузить альбомы. Попробуйте ещё раз.");
  return response.json();
}

function homeAlbumCard(album, index) {
  const link = document.createElement("a");
  link.className = "album-card";
  link.href = `/album/${encodeURIComponent(album.id)}`;

  const cover = document.createElement("div");
  cover.className = "album-cover";
  const photos = [...(Array.isArray(album.photos) ? album.photos : [])]
    .filter((photo) => photo.url)
    .sort((a, b) => a.order_index - b.order_index)
    .slice(0, 3);
  if (photos.length) {
    const mosaic = document.createElement("div");
    mosaic.className = `album-mosaic album-mosaic--${photos.length === 1 ? "single" : photos.length === 2 ? "two" : albumLayouts[index % albumLayouts.length]}`;
    photos.forEach((photo, photoIndex) => {
      const image = document.createElement("img");
      image.className = `album-image ${photoIndex ? `album-mosaic__secondary album-mosaic__secondary--${photoIndex === 1 ? "one" : "two"}` : "album-mosaic__primary"}`;
      image.src = photo.url;
      image.alt = "";
      image.loading = "lazy";
      image.decoding = "async";
      mosaic.append(image);
    });
    cover.append(mosaic);
  } else {
    cover.classList.add("album-cover--empty");
    cover.textContent = "Образы готовятся";
  }

  const info = document.createElement("div");
  info.className = "album-info";
  const meta = document.createElement("div");
  const title = document.createElement("h3");
  title.className = "album-name";
  title.textContent = album.title || "Ваш альбом";
  const date = document.createElement("time");
  date.className = "album-date";
  const parsed = new Date(album.created_at);
  if (!Number.isNaN(parsed.getTime())) {
    date.dateTime = album.created_at;
    date.textContent = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long", year: "numeric" }).format(parsed);
  }
  meta.append(title, date);
  info.append(meta);
  link.append(cover, info);
  return link;
}

function mountHomeAlbums(page, token) {
  const events = new AbortController();
  const grid = page.querySelector("[data-home-albums-grid]");
  const state = page.querySelector("[data-home-albums-state]");
  const message = page.querySelector("[data-home-albums-message]");
  const action = page.querySelector("[data-home-albums-action]");
  const galleryLink = page.querySelector("[data-home-albums-link]");
  grid.replaceChildren();
  galleryLink.hidden = true;
  state.hidden = false;
  action.hidden = true;
  message.textContent = token ? "Загружаем ваши альбомы…" : "Войдите, чтобы увидеть свои альбомы.";
  if (!token) return () => events.abort();

  (async () => {
    try {
      const listing = await requestAlbum("/albums", token, events.signal);
      const results = await Promise.allSettled((listing.album_ids || []).map(
        (id) => requestAlbum(`/albums/${encodeURIComponent(id)}`, token, events.signal),
      ));
      if (events.signal.aborted) return;
      const albums = results.filter((result) => result.status === "fulfilled").map((result) => result.value);
      albums.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
      grid.replaceChildren(...albums.slice(0, 3).map(homeAlbumCard));
      const failed = results.length - albums.length;
      galleryLink.hidden = !albums.length;
      state.hidden = Boolean(albums.length && !failed);
      action.hidden = Boolean(albums.length || failed);
      message.textContent = failed
        ? albums.length ? "Некоторые альбомы не удалось загрузить. Обновите страницу." : "Не удалось загрузить альбомы. Обновите страницу."
        : albums.length ? "" : "Создайте свой первый альбом";
    } catch (error) {
      if (!events.signal.aborted) message.textContent = error.message;
    }
  })();
  return () => events.abort();
}

export function initializeHomeAlbums() {
  const page = document.querySelector(".home-page");
  const token = page ? readSession()?.access_token ?? null : null;
  if (page === albumsPage && token === albumsToken) return;
  releaseHomeAlbums();
  albumsPage = page;
  albumsToken = token;
  if (page) stopAlbums = mountHomeAlbums(page, token);
}

export function releaseHomeAlbums() {
  stopAlbums?.();
  stopAlbums = undefined;
  albumsPage = undefined;
  albumsToken = undefined;
}

const animations = new WeakMap();
const expansionTargets = new WeakMap();
let guideImages = [];
let visibleGuideImages = new Set();
let guideObserver;
let guideMotionListenersReady = false;
const reducedMotionPreference = window.matchMedia("(prefers-reduced-motion: reduce)");

function setExpanded(item, answer, expanded) {
  const isAnimating = expansionTargets.has(item);
  const measuredHeight = answer.getBoundingClientRect().height;
  const currentHeight = isAnimating || item.open ? measuredHeight : 0;
  const computedStyle = getComputedStyle(answer);
  const currentTransform = computedStyle.transform;
  const currentOpacity = currentHeight > 0 ? Number(computedStyle.opacity) : 0;
  animations.get(item)?.cancel();

  answer.style.height = `${currentHeight}px`;
  answer.style.overflow = "hidden";
  if (expanded) item.open = true;
  item.dataset.faqExpanded = String(expanded);
  expansionTargets.set(item, expanded);

  const targetHeight = expanded ? answer.scrollHeight : 0;
  const startTransform = currentHeight < 1 ? "translateY(-8px)" : currentTransform;
  const targetTransform = expanded ? "translateY(0)" : "translateY(-8px)";
  const finish = () => {
    if (expansionTargets.get(item) !== expanded) return;
    if (expanded) {
      item.open = true;
      answer.style.height = "auto";
      answer.style.removeProperty("overflow");
    } else {
      item.open = false;
      answer.style.removeProperty("height");
      answer.style.removeProperty("overflow");
    }
    animations.delete(item);
    expansionTargets.delete(item);
  };

  if (reducedMotionPreference.matches || Math.abs(currentHeight - targetHeight) < 1) {
    finish();
    return;
  }

  if (typeof answer.animate !== "function") {
    const transition = "height 700ms cubic-bezier(0.4, 0, 0.2, 1), opacity 450ms ease, transform 700ms cubic-bezier(0.4, 0, 0.2, 1)";
    let frameHandle;
    let timerHandle;
    const onTransitionEnd = (event) => {
      if (event.target === answer && event.propertyName === "height") finish();
    };
    const cleanup = () => {
      cancelAnimationFrame(frameHandle);
      window.clearTimeout(timerHandle);
      answer.removeEventListener("transitionend", onTransitionEnd);
    };

    answer.style.transition = "none";
    answer.style.height = `${currentHeight}px`;
    answer.style.opacity = String(currentOpacity);
    answer.style.transform = currentTransform === "none" ? startTransform : currentTransform;
    void answer.offsetHeight;
    answer.addEventListener("transitionend", onTransitionEnd);
    animations.set(item, { cancel: cleanup });
    frameHandle = requestAnimationFrame(() => {
      if (expansionTargets.get(item) !== expanded) return;
      answer.style.transition = transition;
      answer.style.height = `${targetHeight}px`;
      answer.style.opacity = expanded ? "1" : "0";
      answer.style.transform = targetTransform;
    });
    timerHandle = window.setTimeout(finish, 800);
    return;
  }

  const animation = answer.animate(
    [
      { height: `${currentHeight}px`, opacity: currentOpacity, transform: startTransform },
      { height: `${targetHeight}px`, opacity: expanded ? 1 : 0, transform: targetTransform },
    ],
    { duration: 700, easing: "cubic-bezier(0.4, 0, 0.2, 1)", fill: "forwards" },
  );
  animations.set(item, animation);
  animation.addEventListener("finish", finish, { once: true });
}

export function initializeHomeFaq() {
  document.querySelectorAll(".home-faq__item").forEach((item) => {
    if (item.dataset.faqInitialized) return;
    const summary = item.querySelector("summary");
    const answer = item.querySelector(".home-faq__answer");
    if (!summary || !answer) return;

    item.dataset.faqInitialized = "true";
    item.dataset.faqExpanded = String(item.open);
    summary.addEventListener("click", (event) => {
      event.preventDefault();
      const currentTarget = expansionTargets.has(item)
        ? expansionTargets.get(item)
        : item.open;
      setExpanded(item, answer, !currentTarget);
    });
  });
}

export function initializeHomeGuideMotion() {
  guideObserver?.disconnect();
  guideImages = [...document.querySelectorAll(".home-guide__vika")];
  visibleGuideImages = new Set();

  if (!guideMotionListenersReady) {
    document.addEventListener("visibilitychange", updateGuidePlayback);
    reducedMotionPreference.addEventListener?.("change", updateGuidePlayback);
    guideMotionListenersReady = true;
  }

  if ("IntersectionObserver" in window) {
    guideObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) visibleGuideImages.add(entry.target);
        else visibleGuideImages.delete(entry.target);
      });
      updateGuidePlayback();
    }, { rootMargin: "100px 0px", threshold: 0.01 });
    guideImages.forEach((image) => guideObserver.observe(image));
  } else {
    visibleGuideImages = new Set(guideImages);
  }

  updateGuidePlayback();
}

function updateGuidePlayback() {
  const canAnimate = !document.hidden && !reducedMotionPreference.matches;
  guideImages.forEach((image) => {
    const source = canAnimate && visibleGuideImages.has(image)
      ? image.dataset.animatedSrc
      : image.dataset.staticSrc;
    if (source && image.getAttribute("src") !== source) image.setAttribute("src", source);
  });
}
