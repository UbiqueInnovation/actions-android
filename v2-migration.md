# v2 Migration Guide

This guide covers breaking changes for callers of the reusable workflows in `.github/workflows/`.

## Breaking Changes Overview

1. **All inputs renamed** from `snake_case`/`camelCase` to `kebab-case`
2. **`android_build_ubdiag_upload.yml` removed** — no replacement
3. **Self-hosted MinIO cache inputs/secrets removed** from all workflows
4. **JDK default changed** from `17` to `21`
5. **Android image default changed** to `2026.03.1-ndk`
6. New input **use-git-lfs** defaults to false

---

## Universal: Input Renames (apply to all workflows)

Every workflow that had `snake_case` or `camelCase` inputs now uses `kebab-case`.

| Old input | New input |
|---|---|
| `android_image_version` | `android-image-version` |
| `appModule` | `app-module` |
| `concurrencyGroup` | `concurrency-group` |
| `workingDirectory` | `working-directory` |
| `workingDirectorySuffix` | `working-directory-suffix` |
| `gradleArgs` | `gradle-args` |
| `libModule` | `lib-module` |
| `versionNameSuffix` | `version-name-suffix` |
| `gradlePropertiesPath` | `gradle-properties-path` |
| `setup_rust_tool_chain` | `setup-rust` |
| `sentry_log_level` | `sentry-log-level` |
| `PRE_BUILD_SCRIPT` | `pre-build-script` |
| `git_branch` | `git-branch` |
| `git_sha` | `git-sha` |
| `runCoeus` | `run-coeus` |
| `skipRules` | `skip-rules` |
| `runTests` | `run-tests` |
| `runLint` | `run-lint` |
| `runSonarqube` | `run-sonarqube` |
| `GITHUB_REPOSITORY` | `github-repository` |

---

## Self-Hosted Cache Removed

The following inputs and secrets have been **removed** from all workflows. Remove them from your callers.

**Inputs removed:**
- `self_hosted_cache_endpoint`
- `self_hosted_cache_port`
- `self_hosted_cache_bucket`
- `self_hosted_cache_region`
- `cacheKeyPrefix`

**Secrets removed:**
- `self_hosted_cache_access_key`
- `self_hosted_cache_secret_key`

Affects: `android_build_alpaka_upload.yml`, `android_gradle_task.yml`, `android_code_quality.yml`

---

## Per-Workflow Changes

### `android_build_ubdiag_upload.yml` — REMOVED

This workflow no longer exists. There is no direct replacement.

---

### `android_build_alpaka_upload.yml`

- All inputs renamed (see table above)
- `jdk` default: `17` → `21`
- `android-image-version` default: `2024.04.1-ndk` → `2026.03.1-ndk`
- Self-hosted cache inputs/secrets removed
- **New optional inputs:** `use-git-lfs` (default `false`)

---

### `android_build_store_upload.yml`

- All inputs renamed (see table above)
- `jdk` default: `17` → `21`
- `android-image-version` default: `2024.04.1-ndk` → `2026.03.1-ndk`
- **New optional inputs:** `use-git-lfs` (default `false`)

---

### `android_code_quality.yml`

- All inputs renamed (see table above)
- `android-image-version` default: `2024.04.1-ndk` → `2026.03.1-ndk`
- Self-hosted cache inputs/secrets removed
- **New optional inputs:** `jdk` (default `21`), `use-git-lfs` (default `false`)

---

### `android_gradle_task.yml`

- All inputs renamed (see table above)
- `android-image-version` default: `2024.04.1-ndk` → `2026.03.1-ndk`
- Self-hosted cache inputs/secrets removed
- **New optional inputs:** `jdk` (default `21`), `use-git-lfs` (default `false`)
- **New optional secret:** `ANDROID_JENKINS_PAT` (falls back to `github.token` if not provided)

---

### `android_library_artifactory.yml`

- All inputs renamed (see table above)
- `jdk` default: `17` → `21`
- **New optional inputs:** `setup-rust` (default `false`), `use-git-lfs` (default `false`)

---

### `multiplatform_library_artifactory.yml`

- All inputs renamed (see table above)
- `jdk` default: `17` → `21`
- **New optional input:** `use-git-lfs` (default `false`)

---

### `alpaka_screenshot_compare.yml`

- `android_image_version` → `android-image-version`, default: `2024.04.1-ndk` → `2026.03.1-ndk`
- **New optional input:** `use-git-lfs` (default `false`)

---

### `github_generate_manual_user_testcases.yml`

- `GITHUB_REPOSITORY` (required) → `github-repository` (required)
