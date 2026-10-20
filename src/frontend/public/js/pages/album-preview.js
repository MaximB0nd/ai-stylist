export const previewAlbums = [
  { id: "office", title: "Офис", situation: "office", styles: ["classic"], shoes: ["loafers"], impressions: ["confident"], created_at: "2026-09-05T12:00:00Z" },
  { id: "evening", title: "Вечер", situation: "evening", styles: ["romantic"], shoes: ["heels"], impressions: ["elegant"], created_at: "2026-09-03T12:00:00Z" },
  { id: "street", title: "Улица", situation: "street", styles: ["casual"], shoes: ["sneakers"], impressions: ["relaxed"], created_at: "2026-09-01T12:00:00Z" },
  { id: "study", title: "Учёба", situation: "study", styles: ["minimal"], shoes: ["boots"], impressions: ["bright"], created_at: "2026-08-28T12:00:00Z" },
].map((album) => ({
  ...album,
  user_age: 25,
  user_height: 170,
  gender: "f",
  source_face_url: "/images/generation/photo-example-face.png",
  source_body_url: "/images/generation/photo-example-body.png",
  photos: Array.from({ length: 5 }, (_, index) => ({
    order_index: index,
    url: `/images/album/look${String(index + 1).padStart(2, "0")}.png`,
  })),
}));

export function previewAlbum(id) {
  return previewAlbums.find((album) => album.id === id);
}
