@echo off
REM -- Open Lakehouse Contract (OLC) Release Script ----------------------
REM Mirrors the LakeLogic (LL) release.bat so both repos cut releases the same way.
REM
REM Usage:   release.bat           (auto-detect bump: patch/minor/major)
REM          release.bat minor     (force minor bump)
REM          release.bat major     (force major bump)
REM
REM Prerequisites:
REM   pip install commitizen
REM   winget install git-cliff     (or: cargo install git-cliff)
REM
REM What it does:
REM   0.  uv lock --upgrade   - pull latest patched dependency versions
REM   0b. pytest              - unit tests (abort if they fail)
REM   0c. conformance         - OLC cross-engine conformance corpus (abort on fail)
REM   0d. ruff check/format   - auto-fix lint & formatting
REM   1.  cz bump             - bumps [project].version in pyproject.toml + git tag
REM   2.  git cliff           - regenerates CHANGELOG.md from all tags (cliff.toml)
REM   3.  git commit amend    - folds changelog into the bump commit
REM   4.  git tag -f          - re-attaches the tag to the amended commit
REM   5.  git push            - pushes everything incl. tags (triggers publish.yml)
REM
REM -----------------------------------------------------------------------
REM IMPORTANT: Commit Message Format
REM -----------------------------------------------------------------------
REM Commits MUST use conventional format for the changelog to work.
REM git-cliff parses commit messages to generate the changelog.
REM
REM Format:  type(scope): description
REM
REM   Types:
REM     feat:     New feature          -> "Added" in changelog
REM     fix:      Bug fix              -> "Fixed" in changelog
REM     docs:     Documentation only   -> "Documentation" in changelog
REM     refactor: Code restructuring   -> "Changed" in changelog
REM     perf:     Performance          -> "Performance" in changelog
REM     test:     Adding/fixing tests  -> "Testing" in changelog
REM     ci:       CI/CD changes        -> "CI/CD" in changelog
REM     build:    Build system changes -> "Build" in changelog
REM     chore:    Maintenance          -> (skipped in changelog)
REM
REM   Examples:
REM     feat: add slaProperties to the OLC schema
REM     feat(validate): report the failing JSON pointer on schema errors
REM     fix(models): make resource_key optional in the strict model
REM     docs: expand the Databricks materialization example
REM -----------------------------------------------------------------------

echo.
echo ======================================================
echo   Open Lakehouse Contract Release
echo ======================================================

REM Step 0: Upgrade dependencies (pull latest security patches)
echo.
echo [0/6] Upgrading dependencies (security patches)...
uv lock --upgrade
if errorlevel 1 (
    echo WARNING: uv lock --upgrade failed. Continuing with existing lockfile.
)
git add uv.lock

REM Step 0b: Unit tests — abort release if they fail
echo.
echo [0b/6] Running tests...
python -m pytest tests/ -x -q --tb=short
if errorlevel 1 (
    echo.
    echo ERROR: Tests failed. Fix them before releasing.
    echo   To revert dep upgrade: git checkout uv.lock
    exit /b 1
)

REM Step 0c: Conformance corpus — the OLC cross-engine gate the publish workflow runs
echo.
echo [0c/6] Running conformance corpus...
python tests/conformance.py
if errorlevel 1 (
    echo.
    echo ERROR: Conformance corpus failed. Do not release with a broken corpus.
    exit /b 1
)

REM Step 0d: Lint and format (auto-fix safe issues)
echo.
echo [0d/6] Running ruff lint and format...
ruff check . --fix --quiet
ruff format . --quiet
git add -u

REM Step 1: Bump version (creates tag + bump commit)
echo.
echo [1/6] Bumping version...
if "%1"=="" (
    python -m commitizen bump --yes
) else (
    python -m commitizen bump --increment %1 --yes
)
if errorlevel 1 (
    echo.
    echo ERROR: cz bump failed.
    echo.
    echo Common causes:
    echo   - No new commits since last tag: commit your changes first
    echo   - Commits not in conventional format: use 'cz commit' or 'feat:/fix:' prefixes
    echo   - Tip: run 'git log --oneline' to check your commits
    echo.
    exit /b 1
)

REM Capture the new tag name (the latest tag on HEAD)
for /f "tokens=*" %%i in ('git describe --tags --abbrev^=0') do set NEW_TAG=%%i
echo   Tag: %NEW_TAG%

REM Step 2: Generate changelog (tag exists on HEAD, so git-cliff sees it)
echo.
echo [2/6] Generating changelog with git-cliff...
git cliff -o CHANGELOG.md
if errorlevel 1 (
    echo ERROR: git cliff failed. Is git-cliff installed? Run: winget install git-cliff
    exit /b 1
)

REM Step 3: Amend the bump commit to include changelog
REM         This creates a NEW commit hash, so the tag is now orphaned
echo.
echo [3/6] Amending bump commit with changelog...
git add CHANGELOG.md
git commit --amend --no-edit

REM Step 4: Re-attach the tag to the amended commit
REM         Without this, the tag points to the old (pre-amend) commit.
REM         Use an ANNOTATED tag (-a): `git push --follow-tags` (step 5) only
REM         pushes annotated tags, so a lightweight `git tag -f` would never reach
REM         origin and the tag-triggered publish.yml/changelog.yml would not fire.
echo.
echo [4/6] Re-tagging %NEW_TAG% on amended commit...
git tag -f -a %NEW_TAG% -m "release %NEW_TAG%"

REM Step 5: Push
echo.
echo [5/6] Pushing to remote...
git push --force --follow-tags

echo.
echo ======================================================
echo   Release %NEW_TAG% complete!
echo ======================================================
echo.
echo   The pushed tag triggers .github/workflows/publish.yml (build + gates +
echo   uv publish via PyPI Trusted Publishing / OIDC - no token) and changelog.yml
echo   (git-cliff regen). Publishing requires the PyPI trusted publisher to exist
echo   for open-lakehouse-contract (add it once as a pending publisher).
echo.
echo   To fix a bad changelog after release:
echo     1. Edit cliff.toml or reword commits
echo     2. git cliff -o CHANGELOG.md
echo     3. git add CHANGELOG.md ^& git commit --amend --no-edit
echo     4. git tag -f %NEW_TAG%
echo     5. git push --force --follow-tags
echo.
