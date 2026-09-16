const PHOTO_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);
const MAX_PHOTO_BYTES = 10 * 1024 * 1024;

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
  const button = page.querySelector(".generation-submit");
  const status = page.querySelector(".generation-status");
  const numbers = [...form.querySelectorAll('input[type="number"]')];
  const groups = [...form.querySelectorAll("[data-question]")];
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

  function updateSummary() {
    const measurements = numbers.filter((input) => input.validity.valid).length;
    const photoCount = photos.filter((photo) => photo.url && !photo.pending).length;
    let choices = 0;
    for (const group of groups) {
      const selected = group.querySelector("input:checked");
      const value = selected?.closest("label").querySelector(".generation-choice-card > span").textContent;
      const output = page.querySelector(`[data-selection="${group.dataset.question}"]`);
      const image = page.querySelector(`[data-selection-image="${group.dataset.question}"]`);
      output.textContent = value || "";
      output.closest("button").setAttribute("aria-label", `Изменить: ${group.querySelector("legend").textContent}${value ? `, ${value}` : ""}`);
      output.closest("dl > div").hidden = !selected;
      image.hidden = !selected;
      if (selected) image.src = selected.closest("label").querySelector("img").src;
      else image.removeAttribute("src");
      if (selected) choices++;
    }
    const total = measurements + photoCount + choices;
    page.querySelector(".generation-selections").hidden = !choices;
    for (const [key, value, max] of [
      ["measurements", measurements, numbers.length],
      ["photos", photoCount, 2],
      ["choices", choices, 4],
    ]) {
      const output = page.querySelector(`[data-count="${key}"]`);
      output.textContent = `${value} / ${max}`;
      output.classList.toggle("is-complete", value === max);
    }
    const maximum = numbers.length + photos.length + groups.length;
    page.querySelector('[data-count="total"]').textContent = `${total} / ${maximum}`;
    const progress = page.querySelector("progress");
    progress.max = maximum;
    progress.value = total;
    progress.textContent = `${total} из ${maximum}`;
    button.disabled = photos.some((photo) => photo.pending);
    status.textContent = "";
  }

  for (const edit of page.querySelectorAll("[data-edit-question]")) {
    edit.addEventListener("click", () => {
      const group = groups.find((item) => item.dataset.question === edit.dataset.editQuestion);
      const input = group.querySelector("input:checked") || group.querySelector("input");
      input.focus({ preventScroll: true });
      group.scrollIntoView({ block: "center", behavior: "instant" });
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
    const group = event.target.closest("[data-question]");
    if (group) error(group, group.dataset.question, "");
    updateSummary();
  }, { signal: events.signal });
  form.addEventListener("blur", (event) => {
    if (numbers.includes(event.target)) validateNumber(event.target);
  }, { capture: true, signal: events.signal });

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    submitted = true;
    if (photos.some((photo) => photo.pending)) {
      status.textContent = "Подождите, фотографии ещё открываются.";
      return;
    }
    const invalid = numbers.filter((input) => !validateNumber(input, true));
    for (const photo of photos) {
      error(photo.input, photo.input.name, photo.url ? "" : "Добавьте фотографию.");
      if (!photo.url) invalid.push(photo.input);
    }
    for (const group of groups) {
      const selected = group.querySelector("input:checked");
      error(group, group.dataset.question, selected ? "" : "Выберите один вариант.");
      if (!selected) invalid.push(group.querySelector("input"));
    }
    status.textContent = invalid.length
      ? "Проверьте отмеченные поля."
      : "Анкета заполнена. Генерация будет доступна после подключения сервиса.";
    // Follow the visible form order when sections are rearranged.
    [...form.querySelectorAll("input")].find((input) => invalid.includes(input))?.focus();
  }, { signal: events.signal });

  photos.forEach(renderPhoto);
  form.dataset.ready = "true";
  updateSummary();
  return () => {
    disposed = true;
    events.abort();
    button.disabled = true;
    photos.forEach((photo) => {
      photo.request++;
      photo.pending = false;
      photo.url = null;
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
