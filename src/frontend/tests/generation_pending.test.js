import test from "node:test";
import assert from "node:assert/strict";

import { forgetPendingGeneration, readPendingGenerations, rememberPendingGeneration } from "../public/js/pages/generation-pending.js";

function withStorage(run) {
  const saved = new Map();
  globalThis.sessionStorage = {
    getItem: (key) => saved.get(key) ?? null,
    setItem: (key, value) => saved.set(key, value),
  };
  try { run(saved); } finally { delete globalThis.sessionStorage; }
}

test("accepted generation is scoped to its account and can be removed", () => withStorage(() => {
  rememberPendingGeneration("generation-1", "user-1");
  assert.deepEqual(readPendingGenerations("user-2"), []);
  assert.equal(readPendingGenerations("user-1")[0].id, "generation-1");
  forgetPendingGeneration("generation-1", "user-1");
  assert.deepEqual(readPendingGenerations("user-1"), []);
}));

test("expired and malformed entries do not appear", () => withStorage((saved) => {
  saved.set("aiStylistPendingGenerations", JSON.stringify([
    { id: "old", userId: "user-1", createdAt: "2000-01-01T00:00:00Z" },
    { id: "bad-date", userId: "user-1", createdAt: "not-a-date" },
  ]));
  assert.deepEqual(readPendingGenerations("user-1"), []);
}));
