import assert from "node:assert/strict";
import test from "node:test";

import {
  measurementError,
  normalizeGenerationFields,
  photoFileError,
  photoSelectionError,
} from "../public/js/pages/generation.js";

test("maps the browser form to the backend generation contract", () => {
  const values = new Map([
    ["age", "28"], ["height", "168"], ["gender", "female"],
    ["occasion", "office"], ["style", "classic"],
    ["shoe", "loafers"], ["mood", "confident"],
  ]);
  assert.deepEqual(normalizeGenerationFields(values), {
    age: "28",
    height: "168",
    gender: "f",
    situation: "office",
    styles: "classic",
    shoes: "loafers",
    impressions: "confident",
  });
});

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

test("does not flag an untouched empty field before submission", () => {
  const field = { name: "age", validity: { valueMissing: true } };
  assert.equal(measurementError(field, false), "");
  assert.equal(measurementError(field), "Укажите возраст.");
});

test("identifies each missing measurement by name", () => {
  for (const [name, label] of [["age", "возраст"], ["height", "рост"]]) {
    assert.equal(measurementError({ name, validity: { valueMissing: true } }), `Укажите ${label}.`);
  }
});

test("reports invalid numeric text before submission", () => {
  assert.equal(measurementError({ validity: { badInput: true, valueMissing: true } }, false), "Введите число.");
});

test("names the out-of-range field and its bounds", () => {
  for (const flag of ["rangeUnderflow", "rangeOverflow"]) {
    assert.equal(measurementError({ name: "height", min: "120", max: "230", validity: { [flag]: true } }), "Укажите рост от 120 до 230.");
  }
});

test("requires integer measurements", () => {
  assert.match(measurementError({ step: "1", validity: { stepMismatch: true } }), /целое/);
  assert.equal(measurementError({ validity: {} }), "");
});

test("rejects multiple dropped photos instead of silently choosing one", () => {
  const photo = { type: "image/png", size: 1024 };
  assert.equal(photoSelectionError([]), "");
  assert.equal(photoSelectionError([photo]), "");
  assert.match(photoSelectionError([photo, photo]), /одну фотографию/);
});
