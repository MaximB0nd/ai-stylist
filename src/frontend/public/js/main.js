import "/js/vendor/pp-reactive-v2.min.js";
import { initializeAuth } from "/js/pages/auth.js?v=front7-2";
import { initializeGeneration, releaseGeneration } from "/js/pages/generation.js?v=front17-1";
import { initializeHomeFaq, initializeHomeGuideMotion } from "/js/pages/home.js?v=front20-5";
import { applyProfilePreferences, initializeProfile } from "/js/pages/profile.js?v=front11-1";

document.addEventListener("pp:navigation:complete", initializeGeneration);
document.addEventListener("pp:navigation:complete", initializeAuth);
document.addEventListener("pp:navigation:complete", initializeHomeFaq);
document.addEventListener("pp:navigation:complete", initializeHomeGuideMotion);
document.addEventListener("pp:navigation:complete", () => {
	initializeProfile();
	applyProfilePreferences();
});
window.addEventListener("pagehide", releaseGeneration);
window.addEventListener("pageshow", () => {
	initializeGeneration();
	initializeAuth();
	initializeHomeFaq();
	initializeHomeGuideMotion();
	initializeProfile();
	applyProfilePreferences();
});

const pp = globalThis.pp;

function mountApp() {
	const app = typeof pp?.getInstance === "function" ? pp.getInstance() : pp;
	app?.mount?.();
}

if (document.readyState !== "loading") {
	mountApp();
	initializeGeneration();
	initializeAuth();
	initializeHomeFaq();
	initializeProfile();
	applyProfilePreferences();
} else {
	document.addEventListener(
		"DOMContentLoaded",
		() => {
			mountApp();
			initializeGeneration();
			initializeAuth();
			initializeHomeFaq();
			initializeHomeGuideMotion();
			initializeProfile();
			applyProfilePreferences();
		},
		{ once: true },
	);
}
