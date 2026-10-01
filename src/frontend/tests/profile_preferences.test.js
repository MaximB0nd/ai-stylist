import assert from "node:assert/strict";
import test from "node:test";

import {
	DEFAULT_PROFILE_PREFERENCES,
	normalizeProfilePreferences,
} from "../public/js/pages/profile.js";

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
