from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from traveller.models import DestinationPool, Settings, Wishlist

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class ConfigBundle:
    settings: Settings
    destinations: DestinationPool
    wishlist: Wishlist


def _read_json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"config file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_config(config_dir: Path) -> ConfigBundle:
    settings = Settings.model_validate(_read_json(config_dir / "settings.json"))
    destinations = DestinationPool.model_validate(_read_json(config_dir / "destinations.json"))
    wishlist = Wishlist.model_validate(_read_json(config_dir / "wishlist.json"))
    return ConfigBundle(settings=settings, destinations=destinations, wishlist=wishlist)
