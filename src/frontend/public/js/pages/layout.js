const SIDEBAR_STORAGE_KEY = "ai-stylist-sidebar-collapsed";
let privacyAnchorObserver = null;

function setSidebarState(collapsed) {
	document.documentElement.classList.toggle("is-sidebar-collapsed", collapsed);
	document.body.classList.toggle("is-sidebar-collapsed", collapsed);
	document.querySelectorAll("[data-sidebar-toggle]").forEach((button) => {
		button.setAttribute("aria-expanded", String(!collapsed));
		button.setAttribute("aria-label", collapsed ? "Раскрыть меню" : "Свернуть меню");
	});
}

function readStoredSidebarState() {
	try {
		return localStorage.getItem(SIDEBAR_STORAGE_KEY) === "true";
	} catch {
		return false;
	}
}

function storeSidebarState(collapsed) {
	try {
		localStorage.setItem(SIDEBAR_STORAGE_KEY, String(collapsed));
	} catch {
		// Ignore storage restrictions and keep the in-page state.
	}
}

function initializePrivacyAnchor() {
	const anchor = document.querySelector(".privacy-anchor");
	const links = [...document.querySelectorAll(".privacy-anchor a[href^='#']")];
	if (!anchor || links.length === 0) {
		privacyAnchorObserver?.disconnect();
		privacyAnchorObserver = null;
		return;
	}

	const sections = links
		.map((link) => {
			const id = link.hash.slice(1);
			const section = id ? document.getElementById(id) : null;
			return section ? { link, section } : null;
		})
		.filter(Boolean);

	if (sections.length === 0) {
		return;
	}

	function setCurrent(sectionId) {
		for (const { link, section } of sections) {
			if (section.id === sectionId) {
				link.setAttribute("aria-current", "true");
			} else {
				link.removeAttribute("aria-current");
			}
		}
	}

	privacyAnchorObserver?.disconnect();
	privacyAnchorObserver = new IntersectionObserver(
		(entries) => {
			const visible = entries
				.filter((entry) => entry.isIntersecting)
				.sort((left, right) => left.boundingClientRect.top - right.boundingClientRect.top)[0];
			if (visible?.target?.id) {
				setCurrent(visible.target.id);
			}
		},
		{
			rootMargin: "-22% 0px -62% 0px",
			threshold: [0, 1],
		},
	);

	for (const { section } of sections) {
		privacyAnchorObserver.observe(section);
	}

	const current = sections
		.slice()
		.reverse()
		.find(({ section }) => section.getBoundingClientRect().top <= window.innerHeight * 0.38);
	setCurrent((current ?? sections[0]).section.id);
}

export function initializeLayout() {
	setSidebarState(readStoredSidebarState());
	document.querySelectorAll("[data-sidebar-toggle]").forEach((button) => {
		if (button.dataset.sidebarReady === "true") {
			return;
		}
		button.dataset.sidebarReady = "true";
		button.addEventListener("click", () => {
			const collapsed = !document.documentElement.classList.contains("is-sidebar-collapsed");
			setSidebarState(collapsed);
			storeSidebarState(collapsed);
		});
	});
	initializePrivacyAnchor();
}
