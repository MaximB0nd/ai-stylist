import assert from "node:assert/strict";
import test from "node:test";

import { photoSelectionError, resolvePhotoSelection } from "../public/js/pages/generation.js";

// A deterministic test replacement for the rule passed to the same consumer.
// It models only the cases below and cannot prove browser decoding or upload.
function fixedPhotoSelectionError(files) {
  if (files.length > 1) return "Выберите одну фотографию для этой области.";
  if (!files.length) return "";
  if (!["image/jpeg", "image/png", "image/webp"].includes(files[0].type)) {
    return "Выберите JPG, PNG или WebP.";
  }
  if (files[0].size > 10 * 1024 * 1024) return "Размер фото не должен превышать 10 МБ.";
  if (!files[0].size) return "Файл пуст. Выберите другую фотографию.";
  return "";
}

const cases = [
  ["normal", [{ type: "image/png", size: 1024 }], ""],
  ["boundary", [{ type: "image/webp", size: 10 * 1024 * 1024 }], ""],
  ["oversize", [{ type: "image/jpeg", size: 10 * 1024 * 1024 + 1 }], "Размер фото не должен превышать 10 МБ."],
  ["empty", [{ type: "image/png", size: 0 }], "Файл пуст. Выберите другую фотографию."],
  ["unsupported", [{ type: "image/gif", size: 1024 }], "Выберите JPG, PNG или WebP."],
  ["multiple", [{ type: "image/png", size: 1024 }, { type: "image/png", size: 1024 }], "Выберите одну фотографию для этой области."],
  ["untouched", [], ""],
];

for (const [implementation, validate] of [
  ["production", photoSelectionError],
  ["fixed test replacement", fixedPhotoSelectionError],
]) {
  for (const [scenario, files, expectedError] of cases) {
    test(`${implementation}: ${scenario}`, () => {
      const original = [...files];
      const decision = resolvePhotoSelection(files, validate);
      assert.equal(decision.error, expectedError);
      assert.equal(decision.file, expectedError || !files.length ? null : files[0]);
      assert.deepEqual(files, original);
    });
  }
}
