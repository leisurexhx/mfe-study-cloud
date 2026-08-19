# GitHub publication runbook

No remote repository, push, deployment, marketplace listing, or release is created automatically.
An owner must review the full tree and Git history, choose the public organization/name, and
explicitly authorize publication.

## Final local checks

```bash
git status --short
python scripts/privacy_scan.py --history
python -m ruff check .
python -m mypy
python -m pytest
python -m bandit -q -r src -c pyproject.toml
python -m pip_audit --skip-editable
python -m build
python -m twine check dist/*
docker compose config --quiet
```

Review `git log --stat --oneline --all` and `git log -p --all`, plus all generated packages. Do
not continue if any credential, personal path, private hostname, real document, note, screenshot,
or identity is present.

## Owner-authorized publication

After the owner creates an empty GitHub repository and confirms the destination:

```bash
git remote add origin git@github.com:OWNER/mfe-study-cloud.git
git push -u origin main
git push origin v1.0.0-rc.1
```

Enable branch protection, required CI, Dependabot, secret scanning, private vulnerability
reporting, and a published security contact. Create release notes from `CHANGELOG.md` and attach
only reproducible, scanned artifacts. Deploy only as a separate explicitly authorized operation.
