export const AUTH_STORAGE_KEY = "aiStylistAuth";
const AUTH_CHANGED_EVENT = "ai-stylist-auth:changed";
const API_BASE = globalThis.AI_STYLIST_API_BASE ?? "/api/v1";

function normalizeSession(value) {
	if (!value || typeof value.access_token !== "string" || !value.access_token.trim()) {
		return null;
	}

	return {
		...value,
		access_token: value.access_token.trim(),
		token_type: "Bearer",
	};
}

export function readSession() {
	try {
		const raw = localStorage.getItem(AUTH_STORAGE_KEY);
		return normalizeSession(raw ? JSON.parse(raw) : null);
	} catch {
		return null;
	}
}

function notifySessionChange(session) {
	window.dispatchEvent(new CustomEvent(AUTH_CHANGED_EVENT, { detail: { session } }));
}

function writeSession(session) {
	const normalized = normalizeSession(session);
	if (!normalized) {
		clearSession();
		return null;
	}

	localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(normalized));
	notifySessionChange(normalized);
	return normalized;
}

function clearSession() {
	localStorage.removeItem(AUTH_STORAGE_KEY);
	notifySessionChange(null);
}

function getErrorMessage(error, fallback) {
	if (typeof error?.detail === "string") {
		return error.detail;
	}
	if (Array.isArray(error?.detail)) {
		return error.detail.map((item) => item.msg ?? "Ошибка валидации").join("; ");
	}
	return fallback;
}

async function requestJson(path, options = {}) {
	const response = await fetch(`${API_BASE}${path}`, {
		...options,
		headers: {
			Accept: "application/json",
			"Content-Type": "application/json",
			...(options.headers ?? {}),
		},
	});

	let payload = null;
	try {
		payload = await response.json();
	} catch {
		payload = null;
	}

	if (!response.ok) {
		throw new Error(getErrorMessage(payload, `Ошибка запроса: ${response.status}`));
	}

	return payload;
}

function getInitials(name) {
	const initials = name
		.trim()
		.split(/\s+/)
		.slice(0, 2)
		.map((part) => part[0])
		.join("")
		.toUpperCase();

	return initials || "A";
}

function formatProfileCreatedAt(value) {
	if (!value) {
		return "—";
	}

	const date = new Date(value);
	if (Number.isNaN(date.getTime())) {
		return "—";
	}

	return new Intl.DateTimeFormat("ru-RU", {
		day: "numeric",
		month: "long",
		year: "numeric",
	}).format(date);
}

export function getProfileViewModel(user) {
	const name = user?.name?.trim() || "Не указано";
	const email = user?.email?.trim() || "Не указана";

	return {
		name,
		email,
		createdAt: formatProfileCreatedAt(user?.created_at),
		initials: user?.name?.trim() ? getInitials(user.name) : "",
	};
}

function setProfileFieldValue(element, value) {
	if ("value" in element && ((typeof HTMLInputElement !== "undefined" && element instanceof HTMLInputElement) || (typeof HTMLTextAreaElement !== "undefined" && element instanceof HTMLTextAreaElement))) {
		element.value = value;
		return;
	}

	element.textContent = value;
}

export function updateProfile(user) {
	const profile = getProfileViewModel(user);

	for (const element of document.querySelectorAll("[data-profile-name]")) {
		setProfileFieldValue(element, profile.name);
	}
	for (const element of document.querySelectorAll("[data-profile-email]")) {
		setProfileFieldValue(element, profile.email);
	}
	for (const element of document.querySelectorAll("[data-profile-created]")) {
		setProfileFieldValue(element, profile.createdAt);
	}
	for (const avatar of document.querySelectorAll("[data-profile-avatar]")) {
		avatar.textContent = profile.initials;
		if (!profile.initials) {
			avatar.innerHTML = '<span class="site-icon site-icon--user-round"></span>';
		}
	}
}

function findElements() {
	const modal = document.getElementById("authModal");
	const form = document.getElementById("loginForm");
	if (!modal || !form) {
		return null;
	}

	return {
		modal,
		form,
		trigger: document.getElementById("authTrigger"),
		title: document.getElementById("authModalTitle"),
		subtitle: document.getElementById("authModalSubtitle"),
		submit: document.getElementById("authSubmit"),
		switchText: document.getElementById("authSwitchText"),
		switchButton: document.getElementById("switchToRegister"),
		nameField: modal.querySelector(".auth-register-field"),
		nameInput: document.getElementById("registerName"),
		emailInput: document.getElementById("loginEmail"),
		passwordInput: document.getElementById("loginPassword"),
		status: document.getElementById("authStatus"),
		accountLabels: document.querySelectorAll("[data-auth-account-label]"),
		avatars: document.querySelectorAll("[data-auth-avatar]"),
	};
}

function updateChrome(user) {
	const elements = findElements();
	const name = user?.name?.trim();
	const email = user?.email?.trim();
	const label = name || email || "Войти";

	for (const accountLabel of elements?.accountLabels ?? []) {
		accountLabel.textContent = label;
	}
	for (const avatar of elements?.avatars ?? []) {
		avatar.textContent = name ? getInitials(name) : "";
		if (!name) {
			avatar.innerHTML = '<span class="site-icon site-icon--user-round"></span>';
		}
	}

	updateProfile(user);
}

export async function loadCurrentUser(session = readSession()) {
	const normalized = normalizeSession(session);
	if (!normalized) {
		updateChrome(null);
		return null;
	}

	if (normalized.user) {
		updateChrome(normalized.user);
	}

	try {
		const user = await requestJson("/auth/me", {
			headers: {
				Authorization: `Bearer ${normalized.access_token}`,
			},
		});
		writeSession({ ...normalized, user });
		updateChrome(user);
		return user;
	} catch {
		clearSession();
		updateChrome(null);
		return null;
	}
}

function setMode(elements, mode) {
	const isRegister = mode === "register";
	elements.form.dataset.mode = mode;
	elements.title.textContent = isRegister ? "Регистрация" : "Вход в аккаунт";
	elements.subtitle.textContent = isRegister ? "Создайте аккаунт, чтобы сохранять образы" : "Добро пожаловать обратно";
	elements.submit.textContent = isRegister ? "Зарегистрироваться" : "Войти";
	elements.switchText.textContent = isRegister ? "Уже есть аккаунт?" : "Пока нет аккаунта?";
	elements.switchButton.textContent = isRegister ? "Войти" : "Зарегистрироваться";
	elements.nameField.hidden = !isRegister;
	elements.nameInput.disabled = !isRegister;
	elements.nameInput.required = isRegister;
	elements.passwordInput.minLength = isRegister ? 8 : 1;
	elements.passwordInput.autocomplete = isRegister ? "new-password" : "current-password";
}

function setStatus(elements, message, tone = "neutral") {
	elements.status.hidden = !message;
	elements.status.textContent = message ?? "";
	elements.status.dataset.tone = tone;
}

function setPending(elements, pending) {
	elements.submit.disabled = pending;
	elements.switchButton.disabled = pending;
	elements.submit.textContent = pending ? "Подождите..." : elements.submit.dataset.idleText;
}

function openModal(elements) {
	setStatus(elements, "");
	elements.modal.hidden = false;
	elements.trigger?.setAttribute("aria-expanded", "true");
	elements.emailInput.focus();
}

function closeModal(elements) {
	elements.modal.hidden = true;
	elements.trigger?.setAttribute("aria-expanded", "false");
	setStatus(elements, "");
}

function toggleMode(elements) {
	setStatus(elements, "");
	setMode(elements, elements.form.dataset.mode === "register" ? "login" : "register");
}

async function submitAuth(elements) {
	if (!elements.form.reportValidity()) {
		return;
	}

	const mode = elements.form.dataset.mode === "register" ? "register" : "login";
	const isRegister = mode === "register";
	const endpoint = isRegister ? "/auth/register" : "/auth/login";
	const body = {
		email: elements.emailInput.value.trim(),
		password: elements.passwordInput.value,
	};

	if (isRegister) {
		body.name = elements.nameInput.value.trim();
	}

	elements.submit.dataset.idleText = elements.submit.textContent;
	setPending(elements, true);
	setStatus(elements, isRegister ? "Создаём аккаунт..." : "Проверяем данные...");

	try {
		const token = await requestJson(endpoint, {
			method: "POST",
			body: JSON.stringify(body),
		});
		const session = writeSession(token);
		await loadCurrentUser(session);
		setStatus(elements, "Готово. Вы вошли в аккаунт.", "success");
		window.setTimeout(() => closeModal(elements), 600);
	} catch (error) {
		setStatus(elements, error.message || "Не удалось войти. Проверьте данные.", "error");
	} finally {
		setPending(elements, false);
	}
}

function handleAuthAction(target) {
	const elements = findElements();
	if (!elements) {
		return false;
	}

	if (target.closest("#authTrigger")) {
		openModal(elements);
		return true;
	}

	if (target.closest("[data-auth-close]")) {
		closeModal(elements);
		return true;
	}

	if (target.closest("#switchToRegister")) {
		toggleMode(elements);
		return true;
	}

	return false;
}

function handleClick(event) {
	if (event.defaultPrevented) {
		return;
	}

	const target = event.target;
	if (!(target instanceof Element)) {
		return;
	}

	handleAuthAction(target);
}

function handleSubmit(event) {
	if (event.defaultPrevented) {
		return;
	}

	if (!(event.target instanceof HTMLFormElement) || event.target.id !== "loginForm") {
		return;
	}

	event.preventDefault();
	const elements = findElements();
	if (elements) {
		void submitAuth(elements);
	}
}

function handleKeydown(event) {
	if (event.defaultPrevented) {
		return;
	}

	const target = event.target;
	if ((event.key === "Enter" || event.key === " ") && target instanceof Element && handleAuthAction(target)) {
		event.preventDefault();
		return;
	}

	if (event.key !== "Escape") {
		return;
	}

	const elements = findElements();
	if (elements && !elements.modal.hidden) {
		closeModal(elements);
	}
}

function bindSessionEvents() {
	if (document.documentElement.dataset.authSessionListeners === "true") {
		return;
	}

	document.documentElement.dataset.authSessionListeners = "true";
	window.addEventListener(AUTH_CHANGED_EVENT, (event) => {
		updateChrome(event.detail?.session?.user ?? null);
	});
	window.addEventListener("storage", (event) => {
		if (event.key !== AUTH_STORAGE_KEY) {
			return;
		}
		void loadCurrentUser(readSession());
	});
}

function bindCurrentElements(elements) {
	if (elements.form.dataset.authBound === "true") {
		return;
	}

	elements.form.dataset.authBound = "true";
	elements.trigger?.addEventListener("click", (event) => {
		event.preventDefault();
		event.stopPropagation();
		openModal(elements);
	});
	elements.modal.querySelectorAll("[data-auth-close]").forEach((node) => {
		node.addEventListener("click", (event) => {
			event.preventDefault();
			event.stopPropagation();
			closeModal(elements);
		});
	});
	elements.switchButton.addEventListener("click", (event) => {
		event.preventDefault();
		event.stopImmediatePropagation();
		toggleMode(elements);
	}, { capture: true });
	elements.form.addEventListener("submit", (event) => {
		event.preventDefault();
		event.stopPropagation();
		void submitAuth(elements);
	});
}

export function initializeAuth() {
	bindSessionEvents();
	const elements = findElements();
	if (!elements) {
		loadCurrentUser(readSession());
		return;
	}

	if (document.documentElement.dataset.authListeners !== "true") {
		document.addEventListener("click", handleClick);
		document.addEventListener("submit", handleSubmit);
		document.addEventListener("keydown", handleKeydown);
		document.documentElement.dataset.authListeners = "true";
	}

	if (elements.form.dataset.authReady !== "true") {
		elements.form.dataset.authReady = "true";
		elements.trigger?.setAttribute("aria-expanded", "false");
		setMode(elements, "login");
	}

	bindCurrentElements(elements);
	void loadCurrentUser(readSession());
}
