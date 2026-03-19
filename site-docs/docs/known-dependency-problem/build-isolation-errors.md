---
icon: lucide/construction
description: "Why packages like suds-jurko fail with 'use_2to3 is invalid' in modern pip/uv, and how odoo-venv installs them with --no-build-isolation."
tags:
  - troubleshooting
  - dependencies
  - build
---

# Build Isolation Errors

## The error

```
error in suds-jurko setup command: use_2to3 is invalid.
```

Or:

```
error: subprocess-exited-with-error
× Getting requirements to build wheel did not run successfully.
```

## Why it happens

Modern pip and uv build packages in **isolated environments** with the latest `setuptools`. Starting from `setuptools` 58.0, the `use_2to3` feature was removed. Older packages like `suds-jurko` and `vatnumber` still use `use_2to3` in their `setup.py`, so they fail to build in isolation.

The key insight: these packages **can** build if they use the `setuptools` version already installed in your venv (which can be pinned to `<58.0`), but pip/uv's build isolation creates a fresh environment with the latest setuptools every time.

## How odoo-venv solves it

odoo-venv maintains a **No Build Isolation (NBI) registry** — a list of packages that need special handling:

| Package | Condition |
|---------|-----------|
| `vatnumber` | Odoo version &le; 13.0 |
| `suds-jurko` | Odoo version &le; 13.0 |
| `magento` | Odoo version &le; 13.0 |
| `rfc6266-parser` | Always |

### What odoo-venv does

1. **Detects NBI packages** in all requirement sources (Odoo's requirements, addons dirs, manifests, extra requirements)
2. **Excludes them** from the batch install
3. For Odoo &le; 13.0, **installs `setuptools<58.0` and `wheel`** into the venv first
4. **Reinstalls NBI packages** one by one with `--no-build-isolation`, so they use the venv's setuptools instead of an isolated one

```
Installing legacy build tools for Odoo <= 13.0...
  ✔  setuptools<58.0 wheel installed

Installing packages that require --no-build-isolation...
  ✔  suds-jurko==0.6 installed (no build isolation)
  ✔  vatnumber==1.2 installed (no build isolation)
```

### Version conditions

The NBI registry uses version markers. `vatnumber` and `suds-jurko` are only flagged for Odoo &le; 13.0 because newer Odoo versions don't depend on them. `rfc6266-parser` is always flagged regardless of Odoo version.

## Manual workaround

```bash
# 1. Install old setuptools into your venv
pip install "setuptools<58.0" wheel

# 2. Install the problematic package without build isolation
pip install --no-build-isolation suds-jurko==0.6
```

!!! note
    The `--no-build-isolation` flag tells pip/uv to use the packages already in the venv for building, instead of creating an isolated build environment. This is why step 1 (installing old setuptools) must come first.
