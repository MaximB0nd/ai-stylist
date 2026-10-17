import assert from "node:assert/strict";
import test from "node:test";

import { measurementError, photoFileError, photoSelectionError } from "../public/js/pages/generation.js";

const LIMIT = 10 * 1024 * 1024;

for (const type of ["image/jpeg", "image/png", "image/webp"]) {
  for (const size of [1, LIMIT - 1, LIMIT]) {
    test(`photo ${type} with ${size} bytes is accepted`, () => {
      assert.equal(photoFileError({ type, size }), "");
    });
  }
}

for (const size of [LIMIT + 1, LIMIT + 1024]) {
  test(`photo above 10 MiB (${size} bytes) is rejected`, () => {
    assert.match(photoFileError({ type: "image/jpeg", size }), /10 МБ/);
  });
}

test("empty photo is rejected at the lower boundary", () => {
  assert.match(photoFileError({ type: "image/png", size: 0 }), /Файл пуст/);
});

for (const type of ["image/gif", "image/svg+xml", "application/octet-stream", ""]) {
  test(`unsupported MIME type ${type || "(empty)"} is rejected`, () => {
    assert.match(photoFileError({ type, size: 1, name: "portrait.png" }), /JPG, PNG или WebP/);
  });
}

test("a selection of two files is rejected even if its first file is valid", () => {
  assert.match(photoSelectionError([{ type: "image/png", size: 1 }, { type: "image/png", size: 1 }]), /одну фотографию/);
});

test("one unsupported file reports its type error", () => {
  assert.match(photoSelectionError([{ type: "image/gif", size: 1 }]), /JPG, PNG или WebP/);
});

test("one empty file reports its size error", () => {
  assert.match(photoSelectionError([{ type: "image/png", size: 0 }]), /Файл пуст/);
});

test("no file selected causes no error before form submission", () => {
  assert.equal(photoSelectionError([]), "");
});

for (const name of ["age", "height"]) {
  test(`missing ${name} is optional before submission and required on submission`, () => {
    const input = { name, validity: { valueMissing: true } };
    assert.equal(measurementError(input, false), "");
    assert.match(measurementError(input, true), /Укажите/);
  });
}

test("bad numeric input takes priority over a missing value", () => {
  assert.equal(measurementError({ validity: { badInput: true, valueMissing: true } }), "Введите число.");
});

for (const flag of ["rangeUnderflow", "rangeOverflow"]) {
  test(`${flag} reports the field's own limits`, () => {
    const input = { name: "height", min: "80", max: "240", validity: { [flag]: true } };
    assert.equal(measurementError(input), "Укажите рост от 80 до 240.");
  });
}

test("fractional measurement is rejected", () => {
  assert.equal(measurementError({ validity: { stepMismatch: true } }), "Введите целое число.");
});

test("valid measurement has no error", () => {
  assert.equal(measurementError({ validity: { valid: true } }), "");
});
