Always commit and push after making a change. Use the fork remote for local changes; origin is upstream.

On macOS, use `bash tools/macos.sh setup <apk-or-apkm>` to build and run without Docker. Use `start`, `stop`, `status`, and `logs` for the existing Lima VM. Its container engine is disabled. Android native libraries require Linux; do not attempt to run them directly on macOS.

Permanent local ports live in ignored `.local/ports.json`. Choose new ports with a cryptographically secure random generator only when first configuring them. The Linux service and session data live on the `wrapper-v2` Lima VM's disk under `/app`; preserve that data across rebuilds.

Keep APKs, NDK downloads, extracted Apple libraries, and session data ignored. Verify native libraries against `LIBS_VERSION.json`. Run `cargo test --locked` and verify `/health?deep=1` and `/me` with Apple initialization enabled after runtime or build changes. Playback readiness is `/me.runtime.playback_ready`; plain `/health` only checks the supervisor. Do not print or save authentication tokens from `/me`.

Prefer pnpm for JavaScript tooling.

`~/.local/bin/gamdl` links to `tools/gamdl.py`. Its original executable is saved in ignored `.local/gamdl.json`. The launcher boots the existing VM without rebuilding, shares it across concurrent jobs, and stops it after the final job exits. Test lifecycle changes with `python3 -m unittest discover -s tests -v`; preserve exit codes and signal cleanup.
