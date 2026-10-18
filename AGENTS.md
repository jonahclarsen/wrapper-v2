Always commit and push after making a change. Use the fork remote for local changes; origin is upstream.

On macOS, use `bash tools/macos.sh setup <apk-or-apkm>` to build and run without Docker. Use `start`, `stop`, `status`, and `logs` for the existing Lima VM. Its container engine is disabled. Android native libraries require Linux; do not attempt to run them directly on macOS.

Permanent local ports live in ignored `.local/ports.json`. Choose new ports with a cryptographically secure random generator only when first configuring them. The Linux service and session data live on the `wrapper-v2` Lima VM's disk under `/app`; preserve that data across rebuilds.

Keep APKs, NDK downloads, extracted Apple libraries, and session data ignored. Verify native libraries against `LIBS_VERSION.json`. Run `cargo test --locked` and verify `/health?deep=1` and `/me` with Apple initialization enabled after runtime or build changes. Playback readiness is `/me.runtime.playback_ready`; plain `/health` only checks the supervisor. Do not print or save authentication tokens from `/me`.

Prefer pnpm for JavaScript tooling.

`~/.local/bin/gamdl` links to `tools/gamdl.py`. Its original executable is saved in ignored `.local/gamdl.json`. Only explicit `--song-codec-priority` values containing `alac` trigger VM startup and automatic `--use-wrapper`. Regular downloads pass through unchanged. Keep the default gamdl config at `use_wrapper = false`, `song_codec_piority = aac-web` (gamdl's spelling). Bash profile aliases `gamdl-lossless` and `gamdl-alac` add `--song-codec-priority alac`. The launcher boots without rebuilding, shares the VM across ALAC jobs, and stops it after the final ALAC job exits. Test lifecycle changes with `python3 -m unittest discover -s tests -v`; preserve exit codes and signal cleanup.
