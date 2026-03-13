---
icon: lucide/network
description: "When installing a package like magento pulls in suds-jurko as a transitive dependency and the build fails. How odoo-venv handles dependency chains."
tags:
  - troubleshooting
  - dependencies
---

# Transitive Dependency Issues

## The error

```
$ pip install magento==3.1

Collecting suds-jurko>=0.6 (from magento==3.1)
  error in suds-jurko setup command: use_2to3 is invalid.
```

You didn't ask for `suds-jurko` — but `magento` depends on it, and it fails to build.

## Why it happens

When pip/uv installs a package, it also installs all of that package's dependencies (called **transitive dependencies**). If any package in the dependency chain requires `--no-build-isolation`, the entire install fails — even though the problematic package was never in your requirements directly.

The dependency chain looks like:

```
Your requirements
  └── magento==3.1
        └── suds-jurko>=0.6  ← fails to build in isolation
```

odoo-venv's NBI (No Build Isolation) detection scans your **direct** requirements. But transitive dependencies aren't visible until pip/uv starts resolving them, which is too late.

## How odoo-venv solves it

odoo-venv adds **parent packages** to the NBI registry when their transitive dependencies are known to need `--no-build-isolation`. In this case, `magento` is registered because it depends on `suds-jurko`:

```python
# From odoo_venv/main.py
_NO_BUILD_ISOLATION_PACKAGES = {
    "vatnumber": "odoo_version <= '13.0'",
    "suds-jurko": "odoo_version <= '13.0'",
    # magento depends on suds-jurko, so the transitive build of suds-jurko
    # also needs the legacy setuptools already present in the venv.
    "magento": "odoo_version <= '13.0'",
    "rfc6266-parser": "",
}
```

When `magento` is detected in any requirement source, odoo-venv:

1. Excludes `magento` from the batch install
2. Installs `setuptools<58.0` and `wheel` in the venv (for Odoo &le; 13.0)
3. Installs `magento` with `--no-build-isolation`
4. This allows `suds-jurko` to also build using the venv's old setuptools

## The `--skip-on-failure` safety net

For transitive dependencies that aren't yet in the NBI registry, `--skip-on-failure` provides a fallback:

```bash
odoo-venv create 12.0 --odoo-dir ~/code/odoo/12.0 --skip-on-failure
```

When a package fails to install, odoo-venv:

1. Parses the error to identify the failing package
2. Removes it from the requirements
3. Retries the install
4. Reports all skipped packages at the end

```
  ⚠  'some-package' failed to install — skipping and retrying...
  ⚠  Skipped 1 package(s) due to installation failure: some-package
```

If the same package keeps failing after being removed (because it's pulled in transitively), odoo-venv stops and reports the issue:

```
  ✗ 'suds-jurko' keeps failing even after being removed from requirements
    (likely a transitive dependency). Giving up.
```

## Manual workaround

```bash
# Install old setuptools first
pip install "setuptools<58.0" wheel

# Install the parent package with --no-build-isolation
pip install --no-build-isolation magento==3.1
```

This works because `--no-build-isolation` applies to the entire dependency tree, not just the top-level package.
