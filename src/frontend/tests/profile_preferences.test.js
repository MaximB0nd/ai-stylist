import assert from "node:assert/strict";
import test from "node:test";

import {
	DEFAULT_PROFILE_PREFERENCES,
	normalizeProfilePreferences,
} from "../public/js/pages/profile.js";
import {
	AUTH_STORAGE_KEY,
	getProfileViewModel,
	readSession,
	updateProfile,
} from "../public/js/pages/auth.js";

test("profile preferences fall back to frontend defaults", () => {
	assert.deepEqual(normalizeProfilePreferences(null), DEFAULT_PROFILE_PREFERENCES);
	assert.deepEqual(normalizeProfilePreferences({ darkMode: "yes" }), DEFAULT_PROFILE_PREFERENCES);
});

test("profile preferences preserve supported boolean values", () => {
	assert.deepEqual(
		normalizeProfilePreferences({ darkMode: true, reduceMotion: true }),
		{ darkMode: true, reduceMotion: true },
	);
});

test("stored auth session normalizes token data", () => {
	const stored = {
		access_token: " token-value ",
		token_type: "bearer",
		user: {
			name: "Мария",
			email: "maria@example.com",
			created_at: "2026-09-20T10:00:00Z",
		},
	};
	globalThis.localStorage = {
		getItem(key) {
			assert.equal(key, AUTH_STORAGE_KEY);
			return JSON.stringify(stored);
		},
	};

	try {
		const session = readSession();
		assert.equal(session.access_token, "token-value");
		assert.equal(session.token_type, "Bearer");
		assert.equal(session.user.email, stored.user.email);
	} finally {
		delete globalThis.localStorage;
	}
});

test("authorized user data populates the profile view", () => {
	const user = {
		name: "Анна Иванова",
		email: "anna@example.com",
		created_at: "2026-09-19T12:00:00Z",
	};
	const viewModel = getProfileViewModel(user);
	assert.equal(viewModel.name, user.name);
	assert.equal(viewModel.email, user.email);
	assert.notEqual(viewModel.createdAt, "—");
	assert.equal(viewModel.initials, "АИ");

	const name = {};
	const email = {};
	const created = {};
	const avatar = {};
	const elements = {
		"[data-profile-name]": [name],
		"[data-profile-email]": [email],
		"[data-profile-created]": [created],
		"[data-profile-avatar]": [avatar],
	};
	globalThis.document = {
		querySelectorAll(selector) {
			return elements[selector] ?? [];
		},
	};

	try {
		updateProfile(user);
		assert.equal(name.textContent, user.name);
		assert.equal(email.textContent, user.email);
		assert.equal(created.textContent, viewModel.createdAt);
		assert.equal(avatar.textContent, "АИ");
	} finally {
		delete globalThis.document;
	}
});

test("profile form inputs receive authorized user data", () => {
	const user = {
		name: "Иван",
		email: "ivan@gmail.com",
		created_at: "2026-10-05T08:00:00Z",
	};
	const nameInput = { value: "Анна Иванова" };
	const emailInput = { value: "anna@example.com" };
	const elements = {
		"[data-profile-name]": [nameInput],
		"[data-profile-email]": [emailInput],
		"[data-profile-created]": [],
		"[data-profile-avatar]": [],
	};
	class TestInputElement {}
	globalThis.HTMLInputElement = TestInputElement;
	globalThis.HTMLTextAreaElement = class TestTextAreaElement {};
	Object.setPrototypeOf(nameInput, TestInputElement.prototype);
	Object.setPrototypeOf(emailInput, TestInputElement.prototype);
	globalThis.document = {
		querySelectorAll(selector) {
			return elements[selector] ?? [];
		},
	};

	try {
		updateProfile(user);
		assert.equal(nameInput.value, user.name);
		assert.equal(emailInput.value, user.email);
	} finally {
		delete globalThis.document;
		delete globalThis.HTMLInputElement;
		delete globalThis.HTMLTextAreaElement;
	}
});
