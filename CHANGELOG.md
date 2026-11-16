# CHANGELOG


## v0.3.0 (2026-11-16)

### Continuous Integration

- Drop --locked from the audit job and sync uv.lock
  ([`a0dffaa`](https://github.com/evertdeman/anondcm/commit/a0dffaadde924c6e30d5f13fcad8ddd950d74303))

semantic-release bumps the version in pyproject.toml on release but not in uv.lock, so the committed
  lock lags one version and `uv audit --locked` breaks after every release. Audit without --locked
  (it still checks for vulnerabilities) and refresh the lock to the current version.

### Features

- Add the DICOM PS3.15 Basic Profile as a ps315 profile
  ([`78b7f03`](https://github.com/evertdeman/anondcm/commit/78b7f03741615f73b08e113b9053ad1b55c4a614))

Add Configuration.ps315() (and a --profile ps315 CLI option) implementing the full PS3.15 Basic
  Confidentiality Profile for header attributes: 561 rules covering the catalogued attributes,
  mapping the Basic Profile action to remove/blank, remapping UIDs, and pseudonymizing key
  identifiers for linkability. The rules are generated from the published DICOM standard
  (innolitics/dicom-standard) via scripts/generate_ps315.py, so they are auditable and reproducible
  rather than hand-written. Pixel data and the PS3.15 pixel/structured-content/date-shifting options
  remain out of scope.


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
