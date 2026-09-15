import "/js/vendor/pp-reactive-v2.min.js";
import { initializeGeneration, releaseGeneration } from "/js/pages/generation.js";

document.addEventListener("pp:navigation:complete", initializeGeneration);
window.addEventListener("pagehide", releaseGeneration);
window.addEventListener("pageshow", initializeGeneration);

const pp = (globalThis).pp;

if (document.readyState !== "loading") {
	pp?.mount?.();
	initializeGeneration();
} else {
	document.addEventListener(
		"DOMContentLoaded",
		() => {
			pp?.mount?.();
			initializeGeneration();
		},
		{ once: true },
	);
}
