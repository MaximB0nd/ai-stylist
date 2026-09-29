import "/js/vendor/pp-reactive-v2.min.js";
import { initializeAuth } from "/js/pages/auth.js";
import { initializeGeneration, releaseGeneration } from "/js/pages/generation.js";

document.addEventListener("pp:navigation:complete", initializeGeneration);
document.addEventListener("pp:navigation:complete", initializeAuth);
window.addEventListener("pagehide", releaseGeneration);
window.addEventListener("pageshow", () => {
	initializeGeneration();
	initializeAuth();
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
} else {
	document.addEventListener(
		"DOMContentLoaded",
		() => {
			mountApp();
			initializeGeneration();
			initializeAuth();
		},
		{ once: true },
	);
}
