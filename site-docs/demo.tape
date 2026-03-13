# odoo-venv terminal demo
# Showcases: create venv for odoo 19 using common preset

# ── Output ────────────────────────────────────────────────────────────────────
Output ./docs/demo.gif

# ── Dependencies ──────────────────────────────────────────────────────────────
Require odoo-venv

# ── Settings ──────────────────────────────────────────────────────────────────
Set Shell bash
Set TypingSpeed 25ms
Set Width 2300
Set Height 1600
Set FontSize 49
Set FontFamily "JetBrains Mono, Fira Code, monospace"
Set Theme { "name": "odoo-venv", "background": "#111111", "foreground": "#f5f5f5", "cursor": "#ea580c", "black": "#2a2a2a", "red": "#ef4444", "green": "#22c55e", "yellow": "#eab308", "blue": "#3b82f6", "magenta": "#d946ef", "cyan": "#06b6d4", "white": "#f5f5f5", "brightBlack": "#52525b", "brightRed": "#f87171", "brightGreen": "#4ade80", "brightYellow": "#facc15", "brightBlue": "#60a5fa", "brightMagenta": "#e879f9", "brightCyan": "#22d3ee", "brightWhite": "#ffffff" }
Set WindowBar Colorful
Set WindowBarSize 60
Set BorderRadius 15
Set Margin 30
Set Padding 40
Set LineHeight 1.3

# ── Scene 1: Create venv for Odoo 19 ──────────────────────────────────────────
Hide
Type "export PS1='\[\033[38;2;249;115;22m\]❯\[\033[0m\] '"
Enter
Type "clear"
Enter
Show

Sleep 500ms
Type "odoo-venv create 19.0 \"
Sleep 400ms
Enter
Type "  --odoo-dir ~/code/odoo/odoo/19.0/ \"
Sleep 400ms
Enter
Type "  --venv-dir ~/code/venvs/19.0 \"
Sleep 400ms
Enter
Type "  --preset common"
Sleep 400ms
Enter

# Give the command time to execute and install dependencies
Sleep 8s
