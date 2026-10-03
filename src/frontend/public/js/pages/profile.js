const PROFILE_PREFERENCES_KEY = "aiStylistProfilePreferences";

export const DEFAULT_PROFILE_PREFERENCES = Object.freeze({
	darkMode: false,
	reduceMotion: false,
});

export function normalizeProfilePreferences(value) {
	return {
		darkMode: typeof value?.darkMode === "boolean" ? value.darkMode : false,
		reduceMotion: typeof value?.reduceMotion === "boolean" ? value.reduceMotion : false,
	};
}

function readProfilePreferences() {
	try {
		return normalizeProfilePreferences(JSON.parse(localStorage.getItem(PROFILE_PREFERENCES_KEY)));
	} catch {
		return { ...DEFAULT_PROFILE_PREFERENCES };
	}
}

function writeProfilePreferences(preferences) {
	localStorage.setItem(PROFILE_PREFERENCES_KEY, JSON.stringify(preferences));
}

export function applyProfilePreferences(preferences = readProfilePreferences()) {
	document.documentElement.toggleAttribute("data-dark-theme", preferences.darkMode);
	document.documentElement.toggleAttribute("data-reduce-motion", preferences.reduceMotion);

	for (const image of document.querySelectorAll("[data-motion-image]")) {
		const source = preferences.reduceMotion
			? image.dataset.staticSrc
			: image.dataset.animatedSrc;
		if (!source) continue;
		if (image.getAttribute("src") !== source) image.setAttribute("src", source);
		if (image.currentSrc && image.currentSrc !== source) image.removeAttribute("srcset");
	}
}

export function initializeProfile() {
	let preferences = readProfilePreferences();
	applyProfilePreferences(preferences);

	const page = document.querySelector(".profile-page");
	if (!page || page.dataset.profileReady === "true") return;

	page.dataset.profileReady = "true";

	for (const input of page.querySelectorAll("[data-profile-preference]")) {
		input.checked = preferences[input.dataset.profilePreference];
		input.addEventListener("change", () => {
			preferences = {
				...preferences,
				[input.dataset.profilePreference]: input.checked,
			};
			writeProfilePreferences(preferences);
			applyProfilePreferences(preferences);
		});
	}
}
