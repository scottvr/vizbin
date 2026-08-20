# Releasing vizbin

vizbin publishes to PyPI through GitHub Actions **Trusted Publishing** (OIDC — no
API token is stored anywhere). Releases are **tag-triggered and gated**: a plain
push or merge to `main` never publishes. Publishing happens only when you push a
`vX.Y.Z` tag whose commit is already on `main`.

## Branching model

- Do feature/fix work on branches → PR → merge to `main`.
- `main` stays releasable at all times.
- A release is a deliberate tag on a `main` commit, not a side effect of merging.

## One-time setup (already in place)

- **PyPI pending publisher**: project `vizbin`, owner `scottvr`, repo `vizbin`,
  workflow `publish-pypi.yml`, environment `pypi`.
- **GitHub `pypi` environment** with `scottvr` as a required reviewer, so the
  upload step pauses for a manual approval click.

## Version — single source of truth

The version lives in exactly one place, `src/vizbin/__init__.py`:

```python
__version__ = "X.Y.Z"
```

`pyproject.toml` reads it via setuptools `dynamic = ["version"]` (`attr`), and the
CLI `--version` uses the same value. **Bump it there and nowhere else.**

Follow [SemVer](https://semver.org/): **MAJOR** for breaking changes, **MINOR**
for new backward-compatible features, **PATCH** for fixes.

## Cutting a release

1. Land the work: feature branch → PR → green CI → merge to `main`.
2. On `main`, bump `__version__` in `src/vizbin/__init__.py`.
3. In `CHANGELOG.md`, move the `[Unreleased]` items under a new `[X.Y.Z]` heading
   (with today's date) and update the link footer.
4. Commit to `main` (this is the one semver-touching commit).
5. (Optional) sanity-check the build locally:
   ```sh
   python -m build && twine check dist/*
   vizbin --version          # -> vizbin X.Y.Z
   rm -rf dist build src/vizbin.egg-info
   ```
6. Tag the release commit and push the tag:
   ```sh
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```
7. The **Publish to PyPI** workflow runs and, before uploading, enforces every gate:
   - full test matrix (Python 3.9–3.14) passes;
   - the tagged commit is an ancestor of `origin/main`;
   - `tag == vX.Y.Z == __version__ == (vizbin --version) == built dist metadata`;
   - `twine check` passes.
8. It then **pauses** in the `pypi` environment. Approve it:
   Actions → the running release → **Review deployments** → **Approve**.
   The package uploads to PyPI with attestations.

## After releasing

- Verify: `pip install vizbin==X.Y.Z`.
- (Optional) create a GitHub Release from the tag, pasting the CHANGELOG section.

## Gotchas

- **PyPI version numbers are permanent.** You cannot re-upload or overwrite
  `X.Y.Z`. If a release is bad, bump to the next PATCH and release again.
- The tag **must** point to a commit already on `main`; the workflow refuses
  otherwise. This is the guard against tagging a pre-merge dev commit (tag first,
  merge later = chaos).
- If the tag and `__version__` disagree, the build job fails *before* publishing.
  Fix `__version__` (or the tag) and re-tag.
- To move a tag before it has published:
  ```sh
  git tag -d vX.Y.Z && git push origin :vX.Y.Z   # delete local + remote tag
  # fix, commit, then re-tag
  ```
- External actions in workflows must be pinned to a full 40-char commit SHA; the
  `Workflow Policy` check enforces this on any workflow change (Dependabot keeps
  the pins current).
