import "/js/vendor/pp-reactive-v2.min.js";
import { initializeAuth } from "/js/pages/auth.js?v=front22-2";
import { initializeAlbum, releaseAlbum } from "/js/pages/album.js?v=front22-35";
import { initializeGeneration, releaseGeneration } from "/js/pages/generation.js?v=front22-3";
import { initializeGallery, releaseGallery } from "/js/pages/gallery.js?v=front22-3";
import { initializeHomeFaq, initializeHomeGuideMotion } from "/js/pages/home.js?v=front20-5";
import { initializeLayout } from "/js/pages/layout.js?v=front19-1";
import { applyProfilePreferences, initializeProfile } from "/js/pages/profile.js?v=front11-1";

document.addEventListener("pp:navigation:complete", initializeGeneration);
document.addEventListener("pp:navigation:complete", initializeAuth);
document.addEventListener("pp:navigation:complete", initializeAlbum);
document.addEventListener("pp:navigation:complete", initializeGallery);
document.addEventListener("pp:navigation:complete", initializeHomeFaq);
document.addEventListener("pp:navigation:complete", initializeHomeGuideMotion);
document.addEventListener("pp:navigation:complete", initializeLayout);
document.addEventListener("pp:navigation:complete", () => {
	initializeProfile();
	applyProfilePreferences();
});
window.addEventListener("pagehide", releaseGeneration);
window.addEventListener("pagehide", releaseAlbum);
window.addEventListener("pagehide", releaseGallery);
window.addEventListener("ai-stylist-auth:changed", () => {
	releaseGallery();
	initializeGallery();
});
window.addEventListener("pageshow", () => {
	initializeGeneration();
	initializeAuth();
	initializeAlbum();
	initializeGallery();
	initializeHomeFaq();
	initializeHomeGuideMotion();
	initializeLayout();
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
	initializeAlbum();
	initializeGallery();
	initializeHomeFaq();
	initializeHomeGuideMotion();
	initializeLayout();
	initializeProfile();
	applyProfilePreferences();
} else {
	document.addEventListener(
		"DOMContentLoaded",
		() => {
			mountApp();
			initializeGeneration();
			initializeAuth();
			initializeAlbum();
			initializeGallery();
			initializeHomeFaq();
			initializeHomeGuideMotion();
			initializeLayout();
			initializeProfile();
			applyProfilePreferences();
		},
		{ once: true },
	);
}
