const STORAGE_KEY = "aiStylistPendingGenerations";
const MAX_AGE_MS = 24 * 60 * 60 * 1000;

export function readPendingGenerations(userId) {
  if (!userId) return [];
  try {
    const saved = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || "[]");
    if (!Array.isArray(saved)) return [];
    return saved.filter((item) => {
      if (!item || item.userId !== userId || typeof item.id !== "string") return false;
      const created = Date.parse(item.createdAt);
      return Number.isFinite(created) && created <= Date.now() && Date.now() - created < MAX_AGE_MS;
    });
  } catch {
    return [];
  }
}

export function rememberPendingGeneration(generationId, userId) {
  if (!generationId || !userId) return;
  try {
    const item = { id: generationId, userId, createdAt: new Date().toISOString() };
    const saved = readPendingGenerations(userId).filter((entry) => entry.id !== generationId);
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify([item, ...saved].slice(0, 20)));
  } catch {
    // The accepted server job still exists if this browser disallows session storage.
  }
}

export function forgetPendingGeneration(generationId, userId) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(
      readPendingGenerations(userId).filter((entry) => entry.id !== generationId),
    ));
  } catch {}
}
