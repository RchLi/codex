#!/usr/bin/env python3
"""Rebrand this Codex fork under a different command name.

The script only performs token replacements, so it can be re-run later with a
different name by passing the current name via ``--from``:

    python3 rebrand/rebrand.py --from codex --name kode --display Kode

What it deliberately does NOT touch:

* the OAuth client id and the ``codex_cli_rs`` originator header, because the
  ChatGPT backend authorizes on those values -- changing them breaks login;
* the ``codex-*`` crate names and the ``CODEX_HOME`` environment variable, so
  the fork stays mergeable with upstream.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class Rebrander:
    def __init__(self, old: str, new: str, old_display: str, new_display: str, dry_run: bool):
        self.old = old
        self.new = new
        self.old_display = old_display
        self.new_display = new_display
        self.dry_run = dry_run
        self.changed: list[str] = []

    # ---- helpers ---------------------------------------------------------

    def _write(self, path: Path, before: str, after: str) -> bool:
        if before == after:
            return False
        rel = path.relative_to(REPO_ROOT).as_posix()
        self.changed.append(rel)
        if not self.dry_run:
            path.write_text(after, encoding="utf-8")
        return True

    def replace_in(self, rel_path: str, pairs: list[tuple[str, str]], required: bool = True) -> None:
        path = REPO_ROOT / rel_path
        if not path.exists():
            if required:
                sys.exit(f"missing expected file: {rel_path}")
            return
        text = path.read_text(encoding="utf-8")
        updated = text
        for needle, replacement in pairs:
            if needle not in updated and required:
                print(f"  note: {rel_path}: pattern not found (already renamed?): {needle!r}")
            updated = updated.replace(needle, replacement)
        self._write(path, text, updated)

    # ---- tier 1: command name, config dir, packaging ---------------------

    def rename_binary(self) -> None:
        self.replace_in(
            "codex-rs/cli/Cargo.toml",
            [(f'\nname = "{self.old}"\n', f'\nname = "{self.new}"\n')],
        )
        self.replace_in(
            "codex-rs/cli/BUILD.bazel",
            [(f'name = "{self.old}",', f'name = "{self.new}",')],
            required=False,
        )
        self.replace_in(
            "codex-rs/cli/src/main.rs",
            [
                (f'bin_name = "{self.old}",', f'bin_name = "{self.new}",'),
                (
                    f'override_usage = "{self.old} [OPTIONS] [PROMPT]\\n       {self.old} [OPTIONS] <COMMAND> [ARGS]"',
                    f'override_usage = "{self.new} [OPTIONS] [PROMPT]\\n       {self.new} [OPTIONS] <COMMAND> [ARGS]"',
                ),
                (f'    let name = "{self.old}";', f'    let name = "{self.new}";'),
            ],
        )
        self.replace_in(
            "justfile",
            [(f"--bin {self.old} ", f"--bin {self.new} ")],
            required=False,
        )

    def rename_config_dir(self) -> None:
        # Single resolution point for the config directory. CODEX_HOME keeps
        # working as an override so the existing test-suite stays green.
        self.replace_in(
            "codex-rs/utils/home-dir/src/lib.rs",
            [(f'"{"."}{self.old}"', f'".{self.new}"')],
        )

    def rename_npm_package(self) -> None:
        path = REPO_ROOT / "codex-cli/package.json"
        if not path.exists():
            return
        text = path.read_text(encoding="utf-8")
        pkg = json.loads(text)
        pkg["name"] = self.new
        launcher = pkg.get("bin", {}).get(self.old)
        if launcher is not None:
            pkg["bin"] = {self.new: launcher}
        pkg["description"] = f"{self.new_display} is a personal coding agent CLI built on OpenAI Codex."
        self._write(path, text, json.dumps(pkg, indent=2) + "\n")

    # ---- tier 2: user-visible display name -------------------------------

    STRING_LITERAL = re.compile(r'"(?:[^"\\\n]|\\.)*"')

    def rename_display_strings(self) -> None:
        word = re.compile(rf"\b{re.escape(self.old_display)}\b")

        def sub_literal(match: re.Match[str]) -> str:
            literal = match.group(0)
            # Leave anything that looks like an identifier, path or env var.
            if "CODEX_" in literal or f"{self.old}_" in literal or f"/{self.old}" in literal:
                return literal
            return word.sub(self.new_display, literal)

        for path in sorted((REPO_ROOT / "codex-rs/tui/src").rglob("*.rs")):
            text = path.read_text(encoding="utf-8")
            self._write(path, text, self.STRING_LITERAL.sub(sub_literal, text))

        # Snapshot expectations must move with the strings they assert on.
        for path in sorted((REPO_ROOT / "codex-rs/tui").rglob("*.snap")):
            text = path.read_text(encoding="utf-8")
            self._write(path, text, word.sub(self.new_display, text))

    def run(self, with_strings: bool) -> None:
        self.rename_binary()
        self.rename_config_dir()
        self.rename_npm_package()
        if with_strings:
            self.rename_display_strings()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--name", required=True, help="new command name, e.g. kode")
    parser.add_argument("--display", help="new display name, defaults to the capitalized command name")
    parser.add_argument("--from", dest="old", default="codex", help="current command name (default: codex)")
    parser.add_argument("--from-display", dest="old_display", help="current display name (default: capitalized --from)")
    parser.add_argument("--no-strings", action="store_true", help="skip renaming user-visible TUI strings")
    parser.add_argument("--dry-run", action="store_true", help="report the files that would change without writing")
    args = parser.parse_args()

    if not re.fullmatch(r"[a-z][a-z0-9-]*", args.name):
        sys.exit("--name must be lowercase alphanumeric with dashes, e.g. kode")

    rebrander = Rebrander(
        old=args.old,
        new=args.name,
        old_display=args.old_display or args.old.capitalize(),
        new_display=args.display or args.name.capitalize(),
        dry_run=args.dry_run,
    )
    rebrander.run(with_strings=not args.no_strings)

    verb = "would change" if args.dry_run else "changed"
    print(f"{verb} {len(rebrander.changed)} files")
    for rel in rebrander.changed[:20]:
        print(f"  {rel}")
    if len(rebrander.changed) > 20:
        print(f"  ... and {len(rebrander.changed) - 20} more")


if __name__ == "__main__":
    main()
