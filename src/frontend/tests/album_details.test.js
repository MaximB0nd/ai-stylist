import test from "node:test";
import assert from "node:assert/strict";

import { albumChoice } from "../public/js/pages/album.js";

test("album choices reuse the selected questionnaire illustration", () => {
  assert.deepEqual(albumChoice("occasion", "office"), {
    label: "Офис",
    image: "/images/generation/occasion-office.webp?v=3",
  });
  assert.deepEqual(albumChoice("style", "minimalism"), {
    label: "Базовый",
    image: "/images/generation/style-minimal.webp?v=3",
  });
});

test("casual style is shown with the Russian label", () => {
  assert.deepEqual(albumChoice("style", "casual"), {
    label: "Удобный",
    image: "/images/generation/style-casual.webp?v=3",
  });
});

test("unknown stored values are shown without inventing a selection image", () => {
  assert.deepEqual(albumChoice("shoe", "unknown"), {
    label: "unknown",
    image: null,
  });
});
