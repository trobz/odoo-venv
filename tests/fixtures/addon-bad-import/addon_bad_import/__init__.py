# Intentional bad import — causes Odoo to log an ERROR during module loading,
# which checklog-odoo will catch and fail the CI step.
import this_package_does_not_exist  # noqa: F401
