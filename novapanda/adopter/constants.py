"""Adopter 共用常量（避免 charge ↔ stations 循环依赖）。"""

ENERGY_RESOURCE = "energy.electric.dc"
ENERGY_RULE = "R-energy-dc-meter-v1"
DEFAULT_ENERGY_PRICE = {"amount": 1050, "currency": "USD"}
