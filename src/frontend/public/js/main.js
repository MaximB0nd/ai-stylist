import "/js/vendor/pp-reactive-v2.min.js";
import { initializeAuth } from "/js/pages/auth.js?v=front7-1";
import { initializeGeneration, releaseGeneration } from "/js/pages/generation.js?v=front4-21";
import { initializeProfile } from "/js/pages/profile.js?v=front7-3";

document.addEventListener("pp:navigation:complete", initializeGeneration);
document.addEventListener("pp:navigation:complete", initializeAuth);
document.addEventListener("pp:navigation:complete", initializeProfile);
window.addEventListener("pagehide", releaseGeneration);
window.addEventListener("pageshow", () => {
	initializeGeneration();
	initializeAuth();
	initializeProfile();
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
	initializeProfile();
} else {
	document.addEventListener(
		"DOMContentLoaded",
		() => {
			mountApp();
			initializeGeneration();
			initializeAuth();
			initializeProfile();
		},
		{ once: true },
	);
}
