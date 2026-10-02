import assert from "node:assert/strict";
import test from "node:test";

import {
	DEFAULT_PROFILE_PREFERENCES,
	normalizeProfilePreferences,
} from "../public/js/pages/profile.js";
import {
	getProfileViewModel,
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
