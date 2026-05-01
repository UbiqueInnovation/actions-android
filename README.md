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

## Migration

- [v2 Migration Guide](v2-migration.md) — human-readable summary of all breaking changes
- [v2 Migration Agent Instructions](v2-migration-agent.md) — instructions for an AI agent to migrate a project automatically
