---
icon: lucide/wrench
description: Common Odoo dependency problems and how odoo-venv solves them automatically.
---

# Overview

Installing Odoo and its addons involves Python dependency management that regularly breaks in predictable ways. **odoo-venv handles all of these automatically** — but understanding them helps when debugging or working without odoo-venv.

## Common problems

| Problem | What goes wrong | Page |
|---------|----------------|------|
| **Import name ≠ package name** | Addon manifest says `git`, pip needs `GitPython` | [Read more](import-name-vs-package-name.md) |
| **Version conflicts** | Odoo pins `pytz==2016.7`, your addon needs `pytz>=2020.1` | [Read more](version-conflicts.md) |
| **Build isolation errors** | `use_2to3 is invalid` when installing old packages | [Read more](build-isolation-errors.md) |
| **Transitive dependency issues** | Installing `magento` pulls `suds-jurko` which fails to build | [Read more](transitive-dependency-issues.md) |

## How odoo-venv helps

Each problem page explains:

1. **The error** — exact terminal output you'd see
2. **Why it happens** — root cause
3. **How odoo-venv solves it** — the automatic mitigation
4. **Manual workaround** — if you're not using odoo-venv
