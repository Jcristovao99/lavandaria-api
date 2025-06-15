"""
laundry_optimizer_final.py
===========================
Otimizador de custos para lavanderia com precário atualizado.
Calcula a combinação mais económica de packs e peças avulsas.

Requer: pulp (pip install pulp)
"""

from __future__ import annotations
from typing import Dict, Tuple, Any
from pulp import LpProblem, LpMinimize, LpInteger, LpVariable, lpSum, LpStatus
import json
import logging

# --------------------------------------------------------------------------- #
#  CATALOGO ATUALIZADO (JUNHO 2025)
# --------------------------------------------------------------------------- #
CATALOG = {
    # Packs mistos (engomar)
    "packs_mistos": [
        {"tipo": "20", "capacidade": 20, "limite_camisas": 5, "preco": 16.0},
        {"tipo": "40", "capacidade": 40, "limite_camisas": 8, "preco": 28.0},
        {"tipo": "60", "capacidade": 60, "limite_camisas": 12, "preco": 39.0},
    ],
    # Packs de camisas
    "packs_camisas": [
        {"tipo": "5", "capacidade": 5, "preco": 6.5},
        {"tipo": "10", "capacidade": 10, "preco": 12.0},
    ],
    # Packs de roupa de cama
    "packs_roupa_cama": [
        {"tipo": "Pequeno", "lencois": 2, "fronha": 4, "preco": 17.0},
        {"tipo": "Grande", "lencois": 3, "fronha": 6, "preco": 24.0},
    ],
    # Preços avulsos
    "avulso": {
        # Engomar
        "peca_variada": 0.90,
        "camisa": 1.80,
        "vestido_simples": 7.00,
        "vestido_com_folhos": 12.50,
        "calca_com_vinco": 3.50,
        "blazer": 4.50,
        "fronha": 2.50,
        "toalha": 2.00,
        "lencois": 3.50,
        # Limpeza + Engomar
        "calca_com_blazer": 12.50,
        "vestido_cerimonia": 12.50,
        "vestido_noiva": 100.00,
        "casaco_sobretudo": 16.90,
        # Só Limpeza
        "blusao_almofadado": 13.00,
        "blusao_penas": 20.00,
    }
}

# --------------------------------------------------------------------------- #
#  NÚCLEO DE OTIMIZAÇÃO
# --------------------------------------------------------------------------- #
class LaundryOptimizer:
    """Otimiza custos de lavanderia usando programação linear inteira."""
    _SPECIALS = [
        # Engomar
        "vestido_simples", "vestido_com_folhos", "calca_com_vinco",
        "blazer", "toalha",
        # Limpeza + Engomar
        "calca_com_blazer", "vestido_cerimonia", "vestido_noiva", "casaco_sobretudo",
        # Só Limpeza
        "blusao_almofadado", "blusao_penas"
    ]
    _OPTIMIZABLE = ["peca_variada", "camisa", "fronha", "lencois"]
    _ITEM_KEYS = list(CATALOG["avulso"].keys())

    def __init__(self, catalog: dict = CATALOG, logger: logging.Logger | None = None):
        self.catalog = catalog
        self.log = logger or logging.getLogger(__name__)

    def optimize_order(
        self,
        items: Dict[str, int],
        solver_name: str | None = None
    ) -> Tuple[float, Dict[str, Any], Dict[str, Any]]:
        order = {k: int(items.get(k, 0)) for k in self._ITEM_KEYS}
        invalid = [k for k in items if k not in order]
        if invalid:
            raise ValueError(f"Itens desconhecidos: {invalid}")

        self.log.info("Processando pedido: %s", order)

        fixed_cost = sum(
            order[item] * self.catalog["avulso"][item]
            for item in self._SPECIALS
        )

        qty = {
            "peca_variada": order["peca_variada"],
            "camisa": order["camisa"],
            "fronha": order["fronha"],
            "lencois": order["lencois"],
        }

        prob = LpProblem("Minimizar_Custo_Lavanderia", LpMinimize)

        # Variáveis de decisão
        x = {
            p["tipo"]: LpVariable(f"pack_misto_{p['tipo']}", 0, cat=LpInteger)
            for p in self.catalog["packs_mistos"]
        }
        s = {
            p["tipo"]: LpVariable(f"camisas_no_misto_{p['tipo']}", 0, cat=LpInteger)
            for p in self.catalog["packs_mistos"]
        }
        y = {
            p["tipo"]: LpVariable(f"pack_camisa_{p['tipo']}", 0, cat=LpInteger)
            for p in self.catalog["packs_camisas"]
        }
        z = {
            p["tipo"]: LpVariable(f"pack_cama_{p['tipo']}", 0, cat=LpInteger)
            for p in self.catalog["packs_roupa_cama"]
        }
        a_var = LpVariable("pecas_variadas_avulsas", 0, cat=LpInteger)
        a_cam = LpVariable("camisas_avulsas", 0, cat=LpInteger)
        a_fronha = LpVariable("fronhas_avulsas", 0, cat=LpInteger)
        a_lencois = LpVariable("lencois_avulsos", 0, cat=LpInteger)

        cost_mistos = lpSum(p["preco"] * x[p["tipo"]] for p in self.catalog["packs_mistos"])
        cost_camisas = lpSum(p["preco"] * y[p["tipo"]] for p in self.catalog["packs_camisas"])
        cost_cama = lpSum(p["preco"] * z[p["tipo"]] for p in self.catalog["packs_roupa_cama"])
        cost_avulso = (
            self.catalog["avulso"]["peca_variada"] * a_var +
            self.catalog["avulso"]["camisa"] * a_cam +
            self.catalog["avulso"]["fronha"] * a_fronha +
            self.catalog["avulso"]["lencois"] * a_lencois
        )

        prob += cost_mistos + cost_camisas + cost_cama + cost_avulso

        # Limite de camisas nos packs mistos
        for p in self.catalog["packs_mistos"]:
            prob += s[p["tipo"]] <= p["limite_camisas"] * x[p["tipo"]]
            prob += s[p["tipo"]] >= 0

        # Cobertura de camisas
        prob += (
            lpSum(s.values()) + 
            lpSum(p["capacidade"] * y[p["tipo"]] for p in self.catalog["packs_camisas"]) + 
            a_cam >= qty["camisa"]
        )

        # Cobertura de peças variadas
        prob += (
            lpSum(
                (p["capacidade"] * x[p["tipo"]]) - s[p["tipo"]] 
                for p in self.catalog["packs_mistos"]
            ) + a_var >= qty["peca_variada"]
        )

        # Cobertura de fronhas
        prob += (
            lpSum(
                pack["fronha"] * z[pack["tipo"]] 
                for pack in self.catalog["packs_roupa_cama"]
            ) + a_fronha >= qty["fronha"]
        )

        # Cobertura de lençóis
        prob += (
            lpSum(
                pack["lencois"] * z[pack["tipo"]] 
                for pack in self.catalog["packs_roupa_cama"]
            ) + a_lencois >= qty["lencois"]
        )

        status = prob.solve(solver_name)
        if LpStatus[status] != "Optimal":
            raise RuntimeError(f"Erro no solver: {LpStatus[status]}")

        packs_mistos = {k: int(v.value()) for k, v in x.items() if v.value() > 0}
        packs_camisas = {k: int(v.value()) for k, v in y.items() if v.value() > 0}
        packs_cama = {k: int(v.value()) for k, v in z.items() if v.value() > 0}

        avulsos = {
            "peca_variada": int(a_var.value()),
            "camisa": int(a_cam.value()),
            "fronha": int(a_fronha.value()),
            "lencois": int(a_lencois.value()),
        }

        camisas_em_mistos = {k: int(v.value()) for k, v in s.items() if v.value() > 0}

        var_cost = prob.objective.value()
        total_cost = round(fixed_cost + var_cost, 2)

        breakdown = {
            "itens_fixos": {k: order[k] for k in self._SPECIALS if order[k] > 0},
            "packs_mistos": packs_mistos,
            "packs_camisas": packs_camisas,
            "packs_roupa_cama": packs_cama,
            "itens_avulsos": avulsos,
            "camisas_em_packs_mistos": camisas_em_mistos,
            "detalhe_custos": {
                "custos_fixos": round(fixed_cost, 2),
                "packs_mistos": round(cost_mistos.value(), 2),
                "packs_camisas": round(cost_camisas.value(), 2),
                "packs_roupa_cama": round(cost_cama.value(), 2),
                "itens_avulsos": round(cost_avulso.value(), 2),
                "total_variavel": round(var_cost, 2),
                "total": total_cost
            }
        }

        return total_cost, breakdown, {v.name: v.value() for v in prob.variables()}

# --------------------------------------------------------------------------- #
#  INTERFACE DE USO
# --------------------------------------------------------------------------- #
def optimizar_pedido(items: Dict[str, int]) -> Tuple[float, Dict[str, Any], Dict[str, Any]]:
    """Função simplificada para otimização direta."""
    return LaundryOptimizer().optimize_order(items)

# --------------------------------------------------------------------------- #
#  CLI PARA TESTES
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Otimizador de Custos de Lavanderia")
    parser.add_argument("--exemplo", action="store_true", help="Executar com pedido exemplo")
    parser.add_argument("--json", type=str, help="Pedido em formato JSON")
    args = parser.parse_args()

    if args.exemplo:
        pedido = {
            "peca_variada": 24,
            "camisa": 9,
            "fronha": 2,
            "lencois": 2,
            "vestido_simples": 3
        }
    elif args.json:
        try:
            pedido = json.loads(args.json)
        except json.JSONDecodeError:
            raise ValueError("JSON inválido")
    else:
        parser.error("Use --exemplo ou --json")

    total, detalhes, _ = optimizar_pedido(pedido)
    print(json.dumps({
        "custo_total": total,
        "detalhes": detalhes
    }, indent=2, ensure_ascii=False))
