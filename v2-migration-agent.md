# v2 Workflows Migration Agent Instructions

You are migrating a project's GitHub Actions workflows from v1 to v2 of the `UbiqueInnovation/actions-android` reusable workflows.

## Your task

1. Find all workflow files in the project's `.github/workflows/` directory that call any reusable workflow from `UbiqueInnovation/actions-android`.
2. Ask the user the clarifying questions listed below **before making any edits**.
3. Apply all changes described in this guide.

---

## Step 1 — Discover caller files

Search `.github/workflows/*.yml` for lines matching:
```
uses: UbiqueInnovation/actions-android/
```
Collect every file and every `uses:` line. Note which reusable workflow each job calls.

---

## Step 2 — Ask the user these questions (before editing anything)

Ask **all** questions upfront in a single message. Do not start editing until you have answers.

### Q1 — Git LFS (required input decision)

> Does this project use **Git LFS** (Large File Storage) to store binary assets (e.g. images, fonts, test fixtures)?
>
> Answer **yes** or **no**.
>
> - If **yes**: `use-git-lfs: true` will be added to every workflow job.
> - If **no**: the input will be omitted (it defaults to `false`).

### Q2 — JDK version

> The default JDK has changed from **17 to 21**. Do you want to keep JDK 17 explicitly, or accept the new default of 21?
>
> - **Accept 21** (recommended): no `jdk:` input needed, remove any existing `jdk: '17'`.
> - **Keep 17**: `jdk: '17'` will be set explicitly on every affected job.

### Q3 — Android image version

> The default Android image has changed to `2026.03.1-ndk`. Do you want to pin a specific version, or accept the new default?
>
> - **Accept new default**: remove any existing `android_image_version:` input.
> - **Pin a version**: provide the version string (e.g. `2026.03.1-ndk`). It will be set as `android-image-version: '<value>'`.

### Q4 — UbDiag upload workflow (only ask if the project calls `android_build_ubdiag_upload.yml`)

> The workflow `android_build_ubdiag_upload.yml` has been **removed** and has no replacement.
> The job calling it cannot be migrated automatically.
>
> How should this job be handled?
> - **Delete the job**: remove it from the workflow file.
> - **Comment it out**: leave it in place but commented out.
> - **Skip**: leave it unchanged (the workflow will be broken until resolved manually).

---

## Step 3 — Apply changes

Work through each discovered caller file. For each file:

### 3a — Remove calls to deleted workflow

If a job uses `android_build_ubdiag_upload.yml`, apply the action chosen in Q4.

### 3b — Rename all inputs (universal)

In every `with:` block under a matching `uses:`, apply these renames. Only rename keys that are actually present; do not add keys that aren't there.

| Old key | New key |
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

### 3c — Remove self-hosted cache inputs and secrets

Remove the following keys from every `with:` block if present:
- `self_hosted_cache_endpoint`
- `self_hosted_cache_port`
- `self_hosted_cache_bucket`
- `self_hosted_cache_region`
- `cacheKeyPrefix`

Remove the following keys from every `secrets:` block if present:
- `self_hosted_cache_access_key`
- `self_hosted_cache_secret_key`

### 3d — Handle JDK input

Based on the answer to Q2:
- **Accept 21**: remove any `jdk: '17'` line. Do not add a `jdk:` line.
- **Keep 17**: if a `jdk:` key is already present, update its value to `'17'`. If it is absent from a job that supports it (all workflows except `alpaka_screenshot_compare` and `github_generate_manual_user_testcases`), add `jdk: '17'` to the `with:` block.

### 3e — Handle android image version input

Based on the answer to Q3:
- **Accept new default**: remove any existing `android_image_version:` or `android-image-version:` line. Do not add one.
- **Pin a version**: rename `android_image_version` to `android-image-version` (already covered by 3b) and ensure the value is set to the pinned version string. If the key was absent, add `android-image-version: '<value>'` to the `with:` block.

### 3f — Handle use-git-lfs input

Based on the answer to Q1:
- **No**: do nothing (the input is absent; it defaults to `false` in the workflow).
- **Yes**: add `use-git-lfs: true` to the `with:` block of every job that calls any of these workflows:
  - `alpaka_screenshot_compare.yml`
  - `android_build_alpaka_upload.yml`
  - `android_build_store_upload.yml`
  - `android_code_quality.yml`
  - `android_gradle_task.yml`
  - `android_library_artifactory.yml`
  - `multiplatform_library_artifactory.yml`

### 3g — Add `workflow_dispatch` trigger if missing

Check the `on:` block of each caller workflow file. If `workflow_dispatch` is not already listed as a trigger, add it. Preserve all existing triggers unchanged.

```yaml
# before
on:
  push:
    branches:
      - main

# after
on:
  push:
    branches:
      - main
  workflow_dispatch:
```

### 3h — Rename workflow name

For each file, rename the workflow's top-level `name:` based on which reusable workflow it calls:

| Reusable workflow called | New workflow name |
|---|---|
| `android_build_store_upload.yml` | "Play Store Upload" |
| `android_build_alpaka_upload.yml` | "Alpaka Build" |
| `android_code_quality.yml` | "Code Quality" |

Preserve any existing tags or platform specifications in the name (e.g., "Android", "(tag)", etc.).

```yaml
# before
name: Android - Build and Upload to Play Store

# after (when the workflow calls android_build_store_upload.yml)
name: Android - Play Store Upload

# before
name: (release) Build

# after
name: (release) Play Store Upload
```

Only change the workflow name; do not modify job names.

---

## Step 4 — Update the `uses:` version pin

For every discovered `uses:` line, update the ref to the newest v2 ref (check https://github.com/UbiqueInnovation/actions-android/tags for the newest v2 tag, or use `@v2.0.0` as a fallback). For example:

```yaml
# before
uses: UbiqueInnovation/actions-android/.github/workflows/android_build_alpaka_upload.yml@v1

# after
uses: UbiqueInnovation/actions-android/.github/workflows/android_build_alpaka_upload.yml@v2.0.0
```

---

## Step 5 — Report

After all edits, report:
- Which files were modified and a brief summary of changes per file.
- Any jobs that were skipped or require manual follow-up (e.g. deleted ubdiag workflow).
- Any input that was present in the old caller but does not exist in v2 at all (flag for manual review).
