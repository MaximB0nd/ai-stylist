const AUTH_STORAGE_KEY = "aiStylistAuth";
const API_BASE = globalThis.AI_STYLIST_API_BASE ?? "/api/v1";

function readSession() {
	try {
		const raw = localStorage.getItem(AUTH_STORAGE_KEY);
		return raw ? JSON.parse(raw) : null;
	} catch {
		return null;
	}
}

function writeSession(session) {
	localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session));
}

function clearSession() {
	localStorage.removeItem(AUTH_STORAGE_KEY);
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
		accountLabel: document.querySelector("[data-auth-account-label]"),
		avatar: document.querySelector("[data-auth-avatar]"),
	};
}

function updateChrome(user) {
	const elements = findElements();
	const name = user?.name?.trim();
	const email = user?.email?.trim();
	const label = name || email || "Мой аккаунт";

	if (elements?.accountLabel) {
		elements.accountLabel.textContent = label;
	}
	if (elements?.avatar) {
		elements.avatar.textContent = name ? getInitials(name) : "";
		if (!name) {
			elements.avatar.innerHTML = '<span class="site-icon site-icon--user-round"></span>';
		}
	}
}

async function loadCurrentUser(session) {
	if (!session?.access_token) {
		updateChrome(null);
		return null;
	}

	try {
		const user = await requestJson("/auth/me", {
			headers: {
				Authorization: `${session.token_type ?? "bearer"} ${session.access_token}`,
			},
		});
		writeSession({ ...session, user });
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
		writeSession(token);
		await loadCurrentUser(token);
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
		setStatus(elements, "");
		setMode(elements, elements.form.dataset.mode === "register" ? "login" : "register");
		return true;
	}

	return false;
}

function handleClick(event) {
	const target = event.target;
	if (!(target instanceof Element)) {
		return;
	}

	handleAuthAction(target);
}

function handleSubmit(event) {
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

function bindCurrentElements(elements) {
	if (elements.form.dataset.authBound === "true") {
		return;
	}

	elements.form.dataset.authBound = "true";
	elements.trigger?.addEventListener("click", () => openModal(elements));
	elements.modal.querySelectorAll("[data-auth-close]").forEach((node) => {
		node.addEventListener("click", () => closeModal(elements));
	});
	elements.switchButton.addEventListener("click", () => {
		setStatus(elements, "");
		setMode(elements, elements.form.dataset.mode === "register" ? "login" : "register");
	});
	elements.form.addEventListener("submit", (event) => {
		event.preventDefault();
		void submitAuth(elements);
	});
}

export function initializeAuth() {
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
