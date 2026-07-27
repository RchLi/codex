# Elva — a personal fork of OpenAI Codex

This repository is a fork of [openai/codex](https://github.com/openai/codex) rebranded
as `elva`. The agent, model backend and authentication are unchanged: it signs in with
the same ChatGPT account and consumes the same quota as the official CLI.

## Building

```shell
cd codex-rs
cargo build --release -p codex-cli
# the binary lands at codex-rs/target/release/elva
```

Put it on your `PATH`, e.g. `ln -s "$PWD/target/release/elva" ~/.local/bin/elva`.

## First run

The config directory is `~/.elva`, isolated from the official CLI's `~/.codex`, so the
first run needs a fresh login:

```shell
elva login
```

To reuse credentials you already have instead of logging in again:

```shell
mkdir -p ~/.elva && cp ~/.codex/auth.json ~/.elva/
```

`CODEX_HOME` still overrides the config directory, and is what the test-suite uses.

## What the rebrand changes

`rebrand/rebrand.py` applies the rename. It is pure token replacement, so a later
rename only takes one command:

```shell
python3 rebrand/rebrand.py --from elva --name newname --display Newname
```

| Surface | Location |
| --- | --- |
| Binary name | `codex-rs/cli/Cargo.toml`, `codex-rs/cli/src/main.rs`, `justfile` |
| Config directory | `codex-rs/utils/home-dir/src/lib.rs` |
| npm package | `codex-cli/package.json` |
| Display name and help text | `codex-rs/{tui,cli,exec}/src` |

Snapshots are deliberately **not** patched textually: they capture fixed-width terminal
output, so a brand name of a different length shifts the trailing padding of every line
it appears on. Regenerate them instead:

```shell
cd codex-rs
RUST_MIN_STACK=8388608 INSTA_UPDATE=always cargo test -p codex-tui -p codex-cli --lib
RUST_MIN_STACK=8388608 INSTA_UPDATE=always cargo test -p codex-cli --bins
```

## What the rebrand deliberately leaves alone

Renaming any of these breaks something:

- **`CLIENT_ID`** (`codex-rs/login/src/auth/manager.rs`) and **`DEFAULT_ORIGINATOR`**
  (`codex-rs/login/src/auth/default_client.rs`). The ChatGPT backend authorizes on
  these two values; changing either breaks login.
- **`codex-*` crate names** and the **`CODEX_HOME`** environment variable. Keeping them
  is what makes `git merge upstream/main` nearly conflict-free.
- **`codex-rs/cli/src/desktop_app/`**. These strings name the official OpenAI Codex
  desktop app — its download URL, the `Codex.app` bundle, the mounted volume — which
  `elva app` still installs. (macOS and Windows only; the module does not exist on
  Linux.)
- **`codex-rs/tui/src/pets/{catalog,picker}.rs`**. "Codex" there is a mascot name tied
  to CDN asset ids, and the picker asserts on the catalog's alphabetical order.
- Backend-facing identifiers such as the `"codex"` rate-limit bucket and MCP
  `use_case` values in `codex-rs/core`.

## Staying current with upstream

```shell
git remote add upstream https://github.com/openai/codex.git
git fetch upstream
git merge upstream/main
python3 rebrand/rebrand.py --name elva --display Elva   # re-apply to new code
```

Then regenerate snapshots as above.

## Known test failure in containers

`doctor::tests::read_probe_file_rejects_unreadable_file` fails when the test suite runs
as root: it `chmod 000`s a file and expects the read to fail, but root reads it anyway.
This is unrelated to the rebrand.
