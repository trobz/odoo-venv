---
icon: lucide/package
description: "Why Odoo addon manifests use import names like 'git' but pip needs 'GitPython' — and the full mapping table."
tags:
  - troubleshooting
  - dependencies
  - manifests
---

# Import Name vs Package Name

## The error

You install an Odoo addon that lists `git` in its `external_dependencies`:

```python
# __manifest__.py
{
    "external_dependencies": {
        "python": ["git"],
    },
}
```

You try to install it:

```
$ pip install git
ERROR: No matching distribution found for git
```

Or worse — you install the wrong package entirely. The Python import name `git` corresponds to the pip package **`GitPython`**, not `git`.

## Why it happens

Odoo addon manifests declare Python dependencies using **import names** (what you write in `import git`), not **pip package names** (what you pass to `pip install GitPython`). These are often different.

In Odoo &le;12.0, the module loader validated dependencies using `importlib.import_module`, so import names were the correct format. Starting from 13.0, manifests should use pip package names — but many addons (especially OCA ports from older versions) still use import names.

## How odoo-venv solves it

odoo-venv maintains a built-in mapping table that automatically translates import names to their correct pip packages. When `--install-addons-manifests-requirements` is enabled, every dependency is looked up against this table before installation.

## Full mapping table

| Import name | Correct pip package |
|-------------|-------------------|
| `stdnum` | `python-stdnum` |
| `crypto` | `pycryptodome` |
| `openssl` | `pyOpenSSL` |
| `dateutil` | `python-dateutil` |
| `yaml` | `pyyaml` |
| `usb` | `pyusb` |
| `serial` | `pyserial` |
| `pil` | `Pillow` |
| `magic` | `python-magic` |
| `bs4` | `beautifulsoup4` |
| `sklearn` | `scikit-learn` |
| `ldap` | `python-ldap` |
| `voicent` | `Voicent-Python` |
| `asterisk` | `py-Asterisk` |
| `facturx` | `factur-x` |
| `mysqldb` | `mysqlclient` |
| `u2flib_server` | `python-u2flib-server` |
| `u2flib-server` | `python-u2flib-server` |
| `git` | `GitPython` |
| `accept_language` | `parse-accept-language` |
| `dns` | `dnspython` |
| `graphql_server` | `graphql-server-core` |

## Manual workaround

If you're not using odoo-venv, check the mapping table above and install the correct pip package manually:

```bash
pip install GitPython    # not "git"
pip install pycryptodome # not "crypto"
pip install Pillow       # not "pil"
```

The lookup is case-insensitive — `Crypto`, `crypto`, and `CRYPTO` all map to `pycryptodome`.
