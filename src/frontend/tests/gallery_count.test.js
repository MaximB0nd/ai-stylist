import test from "node:test";
import assert from "node:assert/strict";

import { previewAlbums } from "../public/js/pages/album-preview.js";

test("development preview provides four albums with two source photos", () => {
  assert.equal(previewAlbums.length, 4);
  for (const album of previewAlbums) {
    assert.equal(album.photos.length, 5);
    assert.ok(album.source_face_url);
    assert.ok(album.source_body_url);
  }
});
