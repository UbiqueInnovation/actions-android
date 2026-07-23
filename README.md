# actions-android

Reusable GitHub Actions workflows for Android (and multiplatform) projects.

## Workflows

| Workflow file | Description |
|---|---|
| `android_build_alpaka_upload.yml` | Build and upload to Alpaka |
| `android_build_store_upload.yml` | Build and upload to Play Store |
| `android_code_quality.yml` | Run code quality checks (lint, tests, Sonarqube) |
| `android_gradle_task.yml` | Run an arbitrary Gradle task |
| `android_library_artifactory.yml` | Build and publish an Android library to Artifactory |
| `multiplatform_library_artifactory.yml` | Build and publish a multiplatform library to Artifactory |
| `alpaka_screenshot_compare.yml` | Screenshot comparison for pull requests |
| `github_generate_manual_user_testcases.yml` | Generate test cases for a PR |

## Usage

Reference any workflow using:

```yaml
jobs:
  build:
    uses: UbiqueInnovation/actions-android/.github/workflows/<workflow-file>@<version>
    with:
      # inputs
    secrets:
      # secrets
```

## Versioning

All actions and reusable workflows are versioned using Semantic Versioning.

- `v2` — floating, always points to the latest `v2.x.x` release
- `v2.0.1` — immutable, pinned to that exact release

Use whichever suits your stability needs:

```yaml
# Stays current within a major version (recommended for most)
uses: UbiqueInnovation/actions-android/.github/workflows/example.yml@v2

# Pinned to an exact release
uses: UbiqueInnovation/actions-android/.github/workflows/example.yml@v2.0.1
```
 
Breaking changes are only introduced in new major versions (`v3`, etc.), so `@v2` will never receive a breaking update.

## Migration Guide

- [v2 Migration Guide](v2-migration.md) — human-readable summary of all breaking changes
- [v2 Migration Agent Instructions](v2-migration-agent.md) — instructions for an AI agent to migrate a project automatically

## Development Notes

- The [internal composite actions](.github/actions) are referenced using the major tag `vX`, thus they must not receive any breaking changes, see also [Issue 70](https://github.com/UbiqueInnovation/actions-android/issues/70).
- Publish a new version by creating a [Release](https://github.com/UbiqueInnovation/actions-android/releases) with the tag `vX.Y.Z`. The floating major tag `vX` will be [updated automatically](https://github.com/UbiqueInnovation/actions-android/actions/workflows/_release_major.yml).
