import { readSession } from "./auth.js";

const PHOTO_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);
const MAX_PHOTO_BYTES = 10 * 1024 * 1024;
const API_BASE = globalThis.AI_STYLIST_API_BASE ?? "/api/v1";
const STATUS_POLL_INTERVAL_MS = 2000;

export function normalizeGenerationFields(data) {
  const gender = data.get("gender");
  return {
    age: data.get("age"),
    height: data.get("height"),
    gender: gender === "female" ? "f" : gender === "male" ? "m" : "",
    situation: data.get("occasion"),
    styles: data.get("style"),
    shoes: data.get("shoe"),
    impressions: data.get("mood"),
  };
}

export function generationFields(form) {
  return normalizeGenerationFields(new FormData(form));
}

function apiError(payload, status) {
  if (typeof payload?.detail === "string") return payload.detail;
  if (Array.isArray(payload?.detail)) {
    return payload.detail.map((item) => item.msg ?? "Ошибка валидации").join("; ");
  }
  return `Ошибка запроса: ${status}`;
}

async function responseJson(response) {
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    // The status code remains useful when an upstream returns a non-JSON error.
  }
  if (!response.ok) throw new Error(apiError(payload, response.status));
  return payload;
}

export function photoFileError(file) {
  if (!PHOTO_TYPES.has(file.type)) return "Выберите JPG, PNG или WebP.";
  if (file.size > MAX_PHOTO_BYTES) return "Размер фото не должен превышать 10 МБ.";
  if (!file.size) return "Файл пуст. Выберите другую фотографию.";
  return "";
}

export function measurementError(input, required = true) {
  const names = { age: "возраст", height: "рост" };
  if (input.validity.badInput) return "Введите число.";
  if (input.validity.valueMissing) return required ? `Укажите ${names[input.name]}.` : "";
  if (input.validity.rangeUnderflow || input.validity.rangeOverflow) {
    return `Укажите ${names[input.name]} от ${input.min} до ${input.max}.`;
  }
  if (input.validity.stepMismatch) {
    return "Введите целое число.";
  }
  return "";
}

export function photoSelectionError(files) {
  if (files.length > 1) return "Выберите одну фотографию для этой области.";
  return files.length ? photoFileError(files[0]) : "";
}

export function mountGeneration(form) {
  const page = form.closest(".generation-page");
  const generationButton = page.querySelector(".generation-generate");
  const status = page.querySelector(".generation-status");
  const numbers = [...form.querySelectorAll('input[type="number"]')];
  const groups = [...form.querySelectorAll("[data-question]")];
  const personalGroups = [...form.querySelectorAll("[data-personal-question]")];
  const events = new AbortController();
  const photos = [...form.querySelectorAll("[data-photo]")].map((element) => ({
    element,
    input: element.querySelector('input[type="file"]'),
    preview: element.querySelector(".generation-preview"),
    url: null,
    request: 0,
    pending: false,
  }));
  const liveUrls = new Set();
  let disposed = false;
  let submitted = false;
  let submitting = false;

  function revoke(url) {
    if (liveUrls.delete(url)) URL.revokeObjectURL(url);
  }

  function error(control, key, message) {
    const text = form.querySelector(`#${key}-error`);
    text.textContent = message;
    text.hidden = !message;
    if (message) control.setAttribute("aria-invalid", "true");
    else control.removeAttribute("aria-invalid");
  }

  function validateNumber(input, required = submitted) {
    const message = measurementError(input, required);
    error(input, input.name, message);
    return !message;
  }

  function pulseInvalidSections() {
    const sections = new Set(
      [...form.querySelectorAll('[aria-invalid="true"]')]
        .map((control) => control.closest("[data-question], .generation-about"))
        .filter(Boolean),
    );
    for (const section of sections) {
      section.classList.remove("is-pulsing");
      void section.offsetWidth;
      section.classList.add("is-pulsing");
    }
  }

  function updateSummary() {
    const measurements = numbers.filter((input) => input.validity.valid).length;
    const personalChoices = personalGroups.filter((group) => group.querySelector("input:checked")).length;
    const photoCount = photos.filter((photo) => photo.url && !photo.pending).length;
    let choices = 0;
    for (const group of groups) {
      const selected = group.querySelector("input:checked");
      const value = selected?.closest("label").querySelector(".generation-choice-card > span").textContent;
      const output = page.querySelector(`[data-selection="${group.dataset.question}"]`);
      const image = page.querySelector(`[data-selection-image="${group.dataset.question}"]`);
      const item = output.closest("dl > div");
      output.textContent = value || "Не выбрано";
      item.classList.toggle("is-empty", !selected);
      image.hidden = !selected;
      if (selected) image.src = selected.closest("label").querySelector("img").src;
      else image.removeAttribute("src");
      if (selected) choices++;
    }
    const total = measurements + personalChoices + photoCount + choices;
    const maximum = numbers.length + personalGroups.length + photos.length + groups.length;
    page.querySelector('[data-count="total"]').textContent = `${total} / ${maximum}`;
    const progress = page.querySelector("progress");
    progress.max = maximum;
    progress.value = total;
    progress.textContent = `${total} из ${maximum}`;
    status.textContent = "";
    delete status.dataset.state;
    generationButton.disabled = submitting || photos.some((photo) => photo.pending);
  }

  const toggleRadios = [...form.querySelectorAll(
    '.generation-choice input[type="radio"], .generation-gender-option input[type="radio"]',
  )];
  const checkedBeforeActivation = new WeakMap(
    toggleRadios.map((radio) => [radio, radio.checked]),
  );
  const syncRadioGroup = (radio) => {
    for (const candidate of toggleRadios) {
      if (candidate.name === radio.name) checkedBeforeActivation.set(candidate, candidate.checked);
    }
  };
  for (const radio of toggleRadios) {
    radio.addEventListener("keydown", (event) => {
      if (event.key !== " " || !radio.checked) return;
      event.preventDefault();
      radio.checked = false;
      radio.dispatchEvent(new Event("change", { bubbles: true }));
    }, { signal: events.signal });
    radio.addEventListener("click", (event) => {
      if (!checkedBeforeActivation.get(radio)) return;
      event.preventDefault();
      setTimeout(() => {
        if (disposed) return;
        radio.checked = false;
        radio.dispatchEvent(new Event("change", { bubbles: true }));
      }, 0);
    }, { capture: true, signal: events.signal });
  }

  for (const button of page.querySelectorAll("[data-edit-question]")) {
    button.addEventListener("click", () => {
      const group = form.querySelector(`[data-question="${button.dataset.editQuestion}"]`);
      const target = group?.querySelector("input:checked") ?? group?.querySelector("input");
      target?.focus();
      group?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, { signal: events.signal });
  }

  function renderPhoto(photo) {
    const hasPhoto = Boolean(photo.url);
    if (hasPhoto) photo.preview.src = photo.url;
    else photo.preview.removeAttribute("src");
    photo.preview.hidden = !hasPhoto;
    photo.element.querySelector(".generation-photo-empty").hidden = hasPhoto;
    photo.element.querySelector("[data-replace-photo]").hidden = !hasPhoto;
    photo.element.querySelector("[data-remove-photo]").hidden = !hasPhoto;
    photo.element.setAttribute("aria-busy", String(photo.pending));
    photo.element.querySelector("[data-photo-status]").textContent = photo.pending
      ? "Открываем фото…" : hasPhoto ? "Фото добавлено" : "";
  }

  function photoError(photo, message) {
    const preserved = message && photo.url ? " Предыдущее фото сохранено." : "";
    error(photo.input, photo.input.name, message + preserved);
  }

  async function acceptPhotos(photo, files) {
    if (!files.length) return;
    // A newer selection, including an invalid one, supersedes an in-flight decode.
    const request = ++photo.request;
    photo.pending = false;
    photo.input.value = "";
    const message = photoSelectionError(files);
    photoError(photo, message);
    if (message) {
      renderPhoto(photo);
      updateSummary();
      return;
    }

    const url = URL.createObjectURL(files[0]);
    liveUrls.add(url);
    photo.pending = true;
    renderPhoto(photo);
    updateSummary();
    try {
      const image = new Image();
      image.src = url;
      await image.decode();
      if (disposed || request !== photo.request) return;
      revoke(photo.url);
      photo.url = url;
      photo.file = files[0];
    } catch {
      if (!disposed && request === photo.request) {
        photoError(photo, "Не удалось открыть фото. Выберите другой файл.");
      }
    } finally {
      if (photo.url !== url) revoke(url);
      if (!disposed && request === photo.request) {
        photo.pending = false;
        renderPhoto(photo);
        updateSummary();
      }
    }
  }

  for (const photo of photos) {
    photo.input.addEventListener("change", () => acceptPhotos(photo, [...photo.input.files]), { signal: events.signal });
    photo.element.addEventListener("dragover", (event) => {
      if (!event.dataTransfer?.types.includes("Files")) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = "copy";
      photo.element.classList.add("is-dragover");
    }, { signal: events.signal });
    photo.element.addEventListener("dragleave", (event) => {
      if (!photo.element.contains(event.relatedTarget)) photo.element.classList.remove("is-dragover");
    }, { signal: events.signal });
    photo.element.addEventListener("drop", (event) => {
      event.preventDefault();
      photo.element.classList.remove("is-dragover");
      acceptPhotos(photo, [...(event.dataTransfer?.files || [])]);
    }, { signal: events.signal });
    photo.element.querySelector("[data-replace-photo]").addEventListener("click", () => photo.input.click(), { signal: events.signal });
    photo.element.querySelector("[data-remove-photo]").addEventListener("click", () => {
      photo.request++;
      photo.pending = false;
      revoke(photo.url);
      photo.url = null;
      photo.file = null;
      photo.input.value = "";
      error(photo.input, photo.input.name, submitted ? "Добавьте фотографию." : "");
      renderPhoto(photo);
      updateSummary();
      photo.input.focus();
    }, { signal: events.signal });
  }

  // Prevent dropped files outside the photo areas from replacing the current page.
  for (const name of ["dragover", "drop"]) {
    page.addEventListener(name, (event) => {
      if (event.dataTransfer?.types.includes("Files")) event.preventDefault();
    }, { signal: events.signal });
  }

  form.addEventListener("input", (event) => {
    const input = event.target;
    if (numbers.includes(input) && (submitted || input.hasAttribute("aria-invalid"))) validateNumber(input);
    updateSummary();
  }, { signal: events.signal });
  form.addEventListener("change", (event) => {
    if (toggleRadios.includes(event.target)) syncRadioGroup(event.target);
    const group = event.target.closest("[data-question]");
    if (group) error(group, group.dataset.question,
      submitted && !group.querySelector("input:checked") ? "Выберите один вариант." : "");
    const personalGroup = event.target.closest("[data-personal-question]");
    if (personalGroup) error(personalGroup, personalGroup.dataset.personalQuestion,
      submitted && !personalGroup.querySelector("input:checked") ? "Выберите один вариант." : "");
    updateSummary();
  }, { signal: events.signal });
  form.addEventListener("blur", (event) => {
    if (numbers.includes(event.target)) validateNumber(event.target);
  }, { capture: true, signal: events.signal });

  async function pollGeneration(generationId) {
    while (!disposed) {
      const session = readSession();
      if (!session) throw new Error("Войдите в аккаунт, чтобы продолжить.");
      const response = await fetch(`${API_BASE}/generations/${generationId}/status`, {
        headers: { Authorization: `Bearer ${session.access_token}` },
        signal: events.signal,
      });
      const current = await responseJson(response);
      if (current.status === "COMPLETED" && current.album_id) {
        status.textContent = "Образы готовы. Открываем альбом…";
        status.dataset.state = "success";
        window.location.assign(`/album/${current.album_id}`);
        return;
      }
      if (current.status === "FAILED" || current.status === "CANCELLED") {
        throw new Error(current.error_message || "Не удалось создать образы.");
      }
      status.textContent = current.status === "DOWNLOADING"
        ? "Сохраняем готовые образы…"
        : "Создаём образы. Это может занять несколько минут…";
      await new Promise((resolve) => window.setTimeout(resolve, STATUS_POLL_INTERVAL_MS));
    }
  }

  async function submitGeneration() {
    const session = readSession();
    if (!session) throw new Error("Войдите в аккаунт, чтобы создать образы.");
    const payload = new FormData();
    for (const [key, value] of Object.entries(generationFields(form))) payload.append(key, value);
    for (const photo of photos) payload.append(`${photo.input.name}_photo`, photo.file, photo.file.name);

    const response = await fetch(`${API_BASE}/generations`, {
      method: "POST",
      headers: { Authorization: `Bearer ${session.access_token}` },
      body: payload,
      signal: events.signal,
    });
    const created = await responseJson(response);
    status.textContent = "Задание принято. Готовим образы…";
    status.dataset.state = "success";
    await pollGeneration(created.generation_id);
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    submitted = true;
    if (photos.some((photo) => photo.pending)) {
      status.textContent = "Подождите, фотографии ещё открываются.";
      status.dataset.state = "error";
      return;
    }
    const invalid = numbers.filter((input) => !validateNumber(input, true));
    for (const photo of photos) {
      error(photo.input, photo.input.name, photo.url ? "" : "Добавьте фотографию.");
      if (!photo.url) invalid.push(photo.input);
    }
    for (const group of personalGroups) {
      const selected = group.querySelector("input:checked");
      error(group, group.dataset.personalQuestion, selected ? "" : "Выберите один вариант.");
      if (!selected) invalid.push(group.querySelector("input"));
    }
    for (const group of groups) {
      const selected = group.querySelector("input:checked");
      error(group, group.dataset.question, selected ? "" : "Выберите один вариант.");
      if (!selected) invalid.push(group.querySelector("input"));
    }
    if (invalid.length) {
      status.textContent = "Заполните подсвеченные блоки.";
      status.dataset.state = "error";
      pulseInvalidSections();
    } else if (!submitting) {
      submitting = true;
      generationButton.disabled = true;
      generationButton.textContent = "Отправляем…";
      status.textContent = "Загружаем фотографии…";
      status.dataset.state = "success";
      void submitGeneration().catch((requestError) => {
        if (disposed || requestError?.name === "AbortError") return;
        status.textContent = requestError?.message || "Не удалось запустить генерацию.";
        status.dataset.state = "error";
        submitting = false;
        generationButton.disabled = false;
        generationButton.textContent = "Сгенерировать 5 образов";
      });
    }
    // Follow the visible form order when sections are rearranged.
    [...form.querySelectorAll("input")].find((input) => invalid.includes(input))?.focus();
  }, { signal: events.signal });

  photos.forEach(renderPhoto);
  form.dataset.ready = "true";
  updateSummary();
  return () => {
    disposed = true;
    events.abort();
    photos.forEach((photo) => {
      photo.request++;
      photo.pending = false;
      photo.url = null;
      photo.file = null;
      photo.input.value = "";
      renderPhoto(photo);
    });
    [...liveUrls].forEach(revoke);
    delete form.dataset.ready;
  };
}

let currentForm;
let dispose;

export function initializeGeneration() {
  const form = document.querySelector("#generation-form");
  if (form === currentForm) return;
  dispose?.();
  currentForm = form;
  dispose = form ? mountGeneration(form) : undefined;
}

export function releaseGeneration() {
  dispose?.();
  dispose = undefined;
  currentForm = undefined;
}
