import sys

# The macOS app runs from Application Support, where its resources and settings are
if getattr(sys, "frozen", False) and sys.platform == "darwin":
    from autosplit64.core.resource_utils import install_mac_app_data
    install_mac_app_data()

from autosplit64.main import main

main()
