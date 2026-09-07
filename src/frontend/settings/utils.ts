import { dirname } from "path";
import { fileURLToPath } from "url";

export const PUBLIC_DIR = "public";
export const SRC_DIR = "src";
export const APP_DIR = "src/app";

export function getFileMeta() {
  const __filename = fileURLToPath(import.meta.url);
  const __dirname = dirname(__filename);
  return { __filename, __dirname };
}
