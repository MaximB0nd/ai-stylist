import test from "node:test";
import assert from "node:assert/strict";
import { apiRequest, generationPayload } from "../public/js/pages/api.js";
import { fetchAlbums, safePhotoUrl } from "../public/js/pages/backend.js";

function session() {
  let data = JSON.stringify({ access_token: "test-token", user: { name: "Test" } });
  globalThis.localStorage = { getItem: () => data, removeItem: () => { data = null; } };
}

test("generation sends the actual files with REST field names and gender", () => {
  const form = new FormData();
  for (const [key, value] of Object.entries({age: "25", height: "175", gender: "female", occasion: "office", style: "casual", shoe: "loafers", mood: "confident"})) form.set(key, value);
  const file = new File(["actual image bytes"], "face.png", {type: "image/png"});
  const result = generationPayload(form, [{input: {name: "face"}, file}, {input: {name: "body"}, file}]);
  assert.equal(result.get("gender"), "f");
  assert.equal(result.get("situation"), "office");
  assert.equal(result.get("styles"), "casual");
  assert.equal(result.get("impressions"), "confident");
  assert.equal(result.get("face_photo").name, "face.png");
  assert.equal(result.get("body_photo").size, file.size);
  assert.equal(result.has("occasion"), false);
});

test("multipart keeps browser boundary and includes bearer token", async () => {
  session();
  globalThis.fetch = async (url, options) => {
    assert.equal(url, "/api/v1/generations");
    assert.equal(options.headers.Authorization, "Bearer test-token");
    assert.equal(options.headers["Content-Type"], undefined);
    return Response.json({generation_id: "accepted"}, {status: 202});
  };
  assert.equal((await apiRequest("/generations", {method: "POST", body: new FormData()})).generation_id, "accepted");
});

test("transient failure preserves the session and does not repeat POST", async () => {
  session();
  let calls = 0;
  globalThis.fetch = async () => { calls++; throw new TypeError("offline"); };
  await assert.rejects(apiRequest("/feedback", {method: "POST", body: "{}"}), /Нет соединения/);
  assert.equal(calls, 1);
  assert.ok(localStorage.getItem("aiStylistAuth"));
});

test("API validation errors reach the form", async () => {
  session();
  globalThis.fetch = async () => Response.json({detail: [{msg: "invalid email"}]}, {status: 422});
  await assert.rejects(apiRequest("/feedback", {method: "POST", body: "{}"}), /invalid email/);
});

test("gallery limits concurrent detail requests and respects home limit", async () => {
  session();
  let active = 0, peak = 0, details = 0;
  globalThis.fetch = async url => {
    if (url === "/api/v1/albums") return Response.json({album_ids: Array.from({length: 10}, (_, i) => String(i))});
    details++; active++; peak = Math.max(peak, active);
    await new Promise(resolve => setTimeout(resolve, 2));
    active--;
    return Response.json({id: url.split("/").pop(), photos: []});
  };
  assert.equal((await fetchAlbums(undefined, 3)).length, 3);
  assert.equal(details, 3);
  details = 0;
  assert.equal((await fetchAlbums()).length, 10);
  assert.ok(peak <= 4);
});

test("photo links reject executable schemes", () => {
  assert.equal(safePhotoUrl("javascript:alert(1)"), "");
  assert.equal(safePhotoUrl("http://192.168.1.1:9000/photo.png?signature=x"), "http://192.168.1.1:9000/photo.png?signature=x");
});
