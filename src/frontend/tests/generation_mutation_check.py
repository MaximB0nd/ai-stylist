"""Run isolated, temporary mutations against the generation validation tests."""

from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "public/js/pages/generation.js"
TEST = ROOT / "tests/generation_lab_validation.test.js"
NODE = shutil.which("node")

MUTATIONS = {
    "D1_allow_oversize": (
        "file.size > MAX_PHOTO_BYTES", "file.size > MAX_PHOTO_BYTES + 1"
    ),
    "D2_accept_empty": (
        'if (!file.size) return "Файл пуст. Выберите другую фотографию.";',
        'if (file.size < 0) return "Файл пуст. Выберите другую фотографию.";',
    ),
    "D3_allow_gif": (
        '"image/jpeg", "image/png", "image/webp"',
        '"image/jpeg", "image/png", "image/webp", "image/gif"',
    ),
    "D4_accept_two_files": (
        "if (files.length > 1)", "if (files.length > 2)"
    ),
    "D5_missing_age_optional": (
        'return required ? `Укажите ${names[input.name]}.` : "";',
        'return required && input.name !== "age" ? `Укажите ${names[input.name]}.` : "";',
    ),
}


def main():
    if not NODE:
        raise SystemExit("Node.js was not found in PATH")
    source = SOURCE.read_text()
    test = TEST.read_text().replace(
        '"../public/js/pages/generation.js"', '"../public/js/pages/generation.js"'
    )
    for name, (old, new) in MUTATIONS.items():
        if source.count(old) != 1:
            raise SystemExit(f"Mutation target is ambiguous: {name}")
        with tempfile.TemporaryDirectory(prefix="generation-mutation-") as temp:
            root = Path(temp)
            (root / "package.json").write_text('{"type":"module"}')
            (root / "public/js/pages").mkdir(parents=True)
            (root / "tests").mkdir()
            (root / "public/js/pages/generation.js").write_text(
                source.replace(old, new)
            )
            (root / "tests/generation_lab_validation.test.js").write_text(test)
            result = subprocess.run(
                [NODE, "--test", "tests/generation_lab_validation.test.js"],
                cwd=root, text=True, capture_output=True, check=False
            )
            failures = [line for line in result.stdout.splitlines()
                        if line.startswith("ℹ fail ")]
            print(f"{name}: {'DETECTED' if result.returncode else 'MISSED'}; "
                  f"{'; '.join(failures) or 'no failure summary'}")


if __name__ == "__main__":
    main()
