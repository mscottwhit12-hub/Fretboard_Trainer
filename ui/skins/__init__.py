"""Registry of available skins (full themes). Add new skins here."""

from ui.skins.pop import PopSkin

SKINS = {s.name: s for s in (PopSkin(),)}
