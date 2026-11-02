---
icon: lucide/hammer
description: "Why old reportlab fails to compile with 'bool cannot be used here' on GCC 15, and how odoo-venv pre-builds it with C17 flags."
tags:
  - troubleshooting
  - dependencies
  - build
---

# Compiler Build Errors

## The error

```
gt1/gt1-parset1.c:1611:13: error: 'bool' cannot be used here
note: 'bool' is a keyword with '-std=c23' onwards
```

On GCC 14 you may instead see:

```
error: passing argument 1 of '_GetStringBuf' from incompatible pointer type [-Wincompatible-pointer-types]
```

## Why it happens

Newer GCC releases are stricter, and the C extensions of `reportlab < 4` break on both changes:

| Since | Change | Affected reportlab |
|-------|--------|--------------------|
| GCC 15 | C23 is the default, so `bool` is a keyword. reportlab's bundled `gt1` parser declares `int bool;` | all 3.x |
| GCC 14 | `-Wincompatible-pointer-types` is an error | 3.5.x, 3.6.x |

This only happens when pip/uv has to **build from source**, because PyPI has no prebuilt wheel for the pinned version and your Python:

| Odoo | reportlab pin | Built from source when |
|------|---------------|------------------------|
| 10.0 &ndash; 12.0 | 3.3.0 | always |
| 13.0 | 3.5.13 | Python &ge; 3.8 |
| 14.0 &ndash; 16.0 | 3.5.13 / 3.5.55 / 3.5.59 | Python &ge; 3.10 |
| 16.0 &ndash; 19.0 | 3.6.x | never |

It can also appear "out of nowhere" on an existing machine: a wheel built earlier is cached, and after a cache clean, a new host, or a uv upgrade, it gets rebuilt without your old workaround flags.

## How odoo-venv solves it

odoo-venv keeps a **build environment registry** of packages that need extra compiler flags, each with a version condition. For reportlab it uses:

```
CFLAGS="-std=gnu17 -Wno-error=incompatible-pointer-types"
```

### What odoo-venv does

1. **Finds reportlab** in the effective requirements (after markers, ignores and overrides are applied)
2. **Installs it on its own** with `uv pip install --no-deps` and the flags above, before the main install
3. **Runs the main install**, which finds reportlab already satisfied and does not rebuild it. Its dependencies (Pillow, etc.) still come from the main install with Odoo's pins

The flags apply only to reportlab, so no other package built in the same run is affected.

```
Pre-building reportlab==3.3.0 with CFLAGS=-std=gnu17 -Wno-error=incompatible-pointer-types...
  ✔  reportlab==3.3.0 installed
```

### Good to know

- A `CFLAGS` already set in your environment **takes precedence**. odoo-venv does not add its own flags in that case, so include `-std=gnu17` yourself if you set it.
- If the pre-build fails, odoo-venv prints a warning and leaves reportlab to the main install, so `--skip-on-failure` keeps working.
- Compilers older than GCC 8 reject `-std=gnu17`. The pre-build then fails and the main install builds reportlab without the flags, which works on those compilers.

## Manual workaround

```bash
# Install reportlab alone with the flags, then the rest as usual
CFLAGS="-std=gnu17 -Wno-error=incompatible-pointer-types" \
  uv pip install --no-deps reportlab==3.3.0

uv pip install -r requirements.txt
```
