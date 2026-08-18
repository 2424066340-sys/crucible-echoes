from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files
from typing import Any


@dataclass(frozen=True)
class Catalog:
    ingredients: dict[str, dict[str, Any]]
    items: dict[str, dict[str, Any]]
    essences: dict[str, dict[str, Any]]
    progression: dict[str, Any]

    @classmethod
    def load(cls) -> "Catalog":
        root = files("crucible_echoes").joinpath("data")

        def read(name: str) -> Any:
            return json.loads(root.joinpath(name).read_text(encoding="utf-8"))

        ingredient_rows = read("ingredients.json")
        item_rows = read("items.json")
        essence_rows = read("essences.json")
        return cls(
            ingredients={row["id"]: row for row in ingredient_rows},
            items={row["id"]: row for row in item_rows},
            essences={row["id"]: row for row in essence_rows},
            progression=read("progression.json"),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        for label, collection in (("ingredient", self.ingredients), ("item", self.items), ("essence", self.essences)):
            for key, row in collection.items():
                if row.get("id") != key:
                    errors.append(f"{label} key mismatch: {key}")
                if not row.get("name"):
                    errors.append(f"{label} lacks name: {key}")
        for essence in self.essences.values():
            item_id = essence.get("item_id")
            if item_id and item_id not in self.items:
                errors.append(f"essence {essence['id']} references missing item {item_id}")
        return errors

