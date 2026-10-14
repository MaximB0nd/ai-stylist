const animations = new WeakMap();
const expansionTargets = new WeakMap();
let guideImages = [];
let visibleGuideImages = new Set();
let guideObserver;
let guideMotionListenersReady = false;
const reducedMotionPreference = window.matchMedia("(prefers-reduced-motion: reduce)");

function setExpanded(item, answer, expanded) {
  const isAnimating = expansionTargets.has(item);
  const measuredHeight = answer.getBoundingClientRect().height;
  const currentHeight = isAnimating || item.open ? measuredHeight : 0;
  const computedStyle = getComputedStyle(answer);
  const currentTransform = computedStyle.transform;
  const currentOpacity = currentHeight > 0 ? Number(computedStyle.opacity) : 0;
  animations.get(item)?.cancel();

  answer.style.height = `${currentHeight}px`;
  answer.style.overflow = "hidden";
  if (expanded) item.open = true;
  item.dataset.faqExpanded = String(expanded);
  expansionTargets.set(item, expanded);

  const targetHeight = expanded ? answer.scrollHeight : 0;
  const startTransform = currentHeight < 1 ? "translateY(-8px)" : currentTransform;
  const targetTransform = expanded ? "translateY(0)" : "translateY(-8px)";
  const finish = () => {
    if (expansionTargets.get(item) !== expanded) return;
    if (expanded) {
      item.open = true;
      answer.style.height = "auto";
      answer.style.removeProperty("overflow");
    } else {
      item.open = false;
      answer.style.removeProperty("height");
      answer.style.removeProperty("overflow");
    }
    animations.delete(item);
    expansionTargets.delete(item);
  };

  if (reducedMotionPreference.matches || Math.abs(currentHeight - targetHeight) < 1) {
    finish();
    return;
  }

  if (typeof answer.animate !== "function") {
    const transition = "height 700ms cubic-bezier(0.4, 0, 0.2, 1), opacity 450ms ease, transform 700ms cubic-bezier(0.4, 0, 0.2, 1)";
    let frameHandle;
    let timerHandle;
    const onTransitionEnd = (event) => {
      if (event.target === answer && event.propertyName === "height") finish();
    };
    const cleanup = () => {
      cancelAnimationFrame(frameHandle);
      window.clearTimeout(timerHandle);
      answer.removeEventListener("transitionend", onTransitionEnd);
    };

    answer.style.transition = "none";
    answer.style.height = `${currentHeight}px`;
    answer.style.opacity = String(currentOpacity);
    answer.style.transform = currentTransform === "none" ? startTransform : currentTransform;
    void answer.offsetHeight;
    answer.addEventListener("transitionend", onTransitionEnd);
    animations.set(item, { cancel: cleanup });
    frameHandle = requestAnimationFrame(() => {
      if (expansionTargets.get(item) !== expanded) return;
      answer.style.transition = transition;
      answer.style.height = `${targetHeight}px`;
      answer.style.opacity = expanded ? "1" : "0";
      answer.style.transform = targetTransform;
    });
    timerHandle = window.setTimeout(finish, 800);
    return;
  }

  const animation = answer.animate(
    [
      { height: `${currentHeight}px`, opacity: currentOpacity, transform: startTransform },
      { height: `${targetHeight}px`, opacity: expanded ? 1 : 0, transform: targetTransform },
    ],
    { duration: 700, easing: "cubic-bezier(0.4, 0, 0.2, 1)", fill: "forwards" },
  );
  animations.set(item, animation);
  animation.addEventListener("finish", finish, { once: true });
}

export function initializeHomeFaq() {
  document.querySelectorAll(".home-faq__item").forEach((item) => {
    if (item.dataset.faqInitialized) return;
    const summary = item.querySelector("summary");
    const answer = item.querySelector(".home-faq__answer");
    if (!summary || !answer) return;

    item.dataset.faqInitialized = "true";
    item.dataset.faqExpanded = String(item.open);
    summary.addEventListener("click", (event) => {
      event.preventDefault();
      const currentTarget = expansionTargets.has(item)
        ? expansionTargets.get(item)
        : item.open;
      setExpanded(item, answer, !currentTarget);
    });
  });
}

export function initializeHomeGuideMotion() {
  guideObserver?.disconnect();
  guideImages = [...document.querySelectorAll(".home-guide__vika")];
  visibleGuideImages = new Set();

  if (!guideMotionListenersReady) {
    document.addEventListener("visibilitychange", updateGuidePlayback);
    reducedMotionPreference.addEventListener?.("change", updateGuidePlayback);
    guideMotionListenersReady = true;
  }

  if ("IntersectionObserver" in window) {
    guideObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) visibleGuideImages.add(entry.target);
        else visibleGuideImages.delete(entry.target);
      });
      updateGuidePlayback();
    }, { rootMargin: "100px 0px", threshold: 0.01 });
    guideImages.forEach((image) => guideObserver.observe(image));
  } else {
    visibleGuideImages = new Set(guideImages);
  }

  updateGuidePlayback();
}

function updateGuidePlayback() {
  const canAnimate = !document.hidden && !reducedMotionPreference.matches;
  guideImages.forEach((image) => {
    const source = canAnimate && visibleGuideImages.has(image)
      ? image.dataset.animatedSrc
      : image.dataset.staticSrc;
    if (source && image.getAttribute("src") !== source) image.setAttribute("src", source);
  });
}
