# CHANGELOG


## v0.2.0 (2026-11-16)

### Continuous Integration

- Let the publish job build instead of semantic-release
  ([`1d297a8`](https://github.com/evertdeman/anondcm/commit/1d297a8481aceeeff25dae158b73b3b11fbc9e60))

semantic-release runs build_command inside its own container, which has no uv, so `uv build` failed
  with exit 127 and aborted the release. Clear the build command; the publish job in the versioning
  workflow builds and uploads with uv instead.

- Publish to PyPI via trusted publishing on release
  ([`2277ac7`](https://github.com/evertdeman/anondcm/commit/2277ac71e5f67d79761f904597cd10047aabbc21))

Add a publish job to the versioning workflow that runs only when semantic-release cuts a new
  version, builds with uv, and uploads to PyPI using OIDC trusted publishing (no API tokens).
  Keeping it in the same workflow run avoids the GITHUB_TOKEN limitation where releases created by
  the default token do not trigger separate workflows.

### Features

- Add a --version flag to the CLI
  ([`9322ddb`](https://github.com/evertdeman/anondcm/commit/9322ddbd3e66a3f37c48d3fa92d16269f4c880ab))

Expose the installed package version as anondcm.__version__ and print it via `anondcm --version`.


## v0.1.0 (2026-11-16)
