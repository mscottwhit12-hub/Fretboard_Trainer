"""
ui/disclosure.py

Always-visible badge disclosing that this app's code was built with AI.
Vendor-neutral, fixed-size, painted by the active skin like any other
badge, and placed in the sidebar so it is visible on every page.
"""

from ui.kit import Badge


class AIDisclosureBanner(Badge):
    def __init__(self, parent=None):
        super().__init__("Built with AI assistance", "white", parent)
