import assert from "node:assert/strict";
import test from "node:test";

import { photoFileError } from "../public/js/pages/generation.js";

for (const type of ["image/jpeg", "image/png", "image/webp"]) {
  test(`accepts nonempty ${type} files`, () => {
    assert.equal(photoFileError({ type, size: 1024 }), "");
  });
}

test("accepts the exact 10 MiB boundary", () => {
  assert.equal(photoFileError({ type: "image/png", size: 10 * 1024 * 1024 }), "");
});

test("rejects a file one byte over the limit", () => {
  assert.match(photoFileError({ type: "image/png", size: 10 * 1024 * 1024 + 1 }), /10 МБ/);
});

test("rejects empty files", () => {
  assert.match(photoFileError({ type: "image/webp", size: 0 }), /пуст/);
});

test("rejects other and missing media types even with an image extension", () => {
  for (const type of ["", "text/plain", "image/svg+xml", "image/gif", "application/octet-stream"]) {
    assert.match(photoFileError({ name: "photo.png", type, size: 1024 }), /JPG, PNG или WebP/);
  }
});
