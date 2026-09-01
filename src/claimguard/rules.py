from __future__ import annotations

from dataclasses import dataclass
import json
from importlib import resources


@dataclass(frozen=True)
class Rule:
    id: str
    name: str
    category: str
    risk_level: str
    detection: str
    judgment: str
    outputs: list[str]
    test_focus: str
    hero_case: bool = False


@dataclass(frozen=True)
class RuleCatalog:
    rules: list[Rule]

    def get(self, rule_id: str) -> Rule:
        for rule in self.rules:
            if rule.id == rule_id:
                return rule
        raise KeyError(rule_id)


def load_rule_catalog() -> RuleCatalog:
    with resources.files("claimguard.data").joinpath("v1_rules.json").open(
        encoding="utf-8"
    ) as file:
        raw_rules = json.load(file)

    return RuleCatalog(rules=[Rule(**raw_rule) for raw_rule in raw_rules])

