"""
laundry_optimizer_final.py
===========================
Otimizador de custos para lavanderia com precário atualizado (Julho 2025)
Calcula a combinação mais económica de packs e peças avulsas.

Requer: pulp (pip install pulp)
"""

from __future__ import annotations
from typing import Dict, Tuple, Any
from pulp import LpProblem, LpMinimize, LpInteger, LpVariable, lpSum, LpStatus
import json
import logging
import numpy as np

# --------------------------------------------------------------------------- #
#  CATALOGO ATUALIZADO (JULHO 2025)
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
    # Preços avulsos
    "avulso": {
        "peca_variada": 0.90,
        "camisa": 1.80,
        "vestido_simples": 3.50,
        "calca_com_vinco": 3.50,
        "blazer": 4.50,
        "toalha_ou_lencol": 1.50,
        "capa_de_edredon": 3.50,
        "calca_com_blazer": 12.50,
        "vestido_cerimonia": 12.50,
        "vestido_noiva": 100.00,
        "casaco_sobretudo": 16.90,
        "blusao_almofadado": 13.00,
        "blusao_penas": 20.00
    }
}

# --------------------------------------------------------------------------- #
#  NÚCLEO DE OTIMIZAÇÃO
# --------------------------------------------------------------------------- #
class LaundryOptimizer:
    """Otimiza custos de lavanderia usando programação linear inteira."""
    _SPECIALS = [
        "vestido_simples", "calca_com_vinco", "blazer", 
        "toalha_ou_lencol", "capa_de_edredon",
        "calca_com_blazer", "vestido_cerimonia", 
        "vestido_noiva", "casaco_sobretudo",
        "blusao_almofadado", "blusao_penas"
    ]
    
    _OPTIMIZABLE = ["peca_variada", "camisa"]
    
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
        a_var = LpVariable("pecas_variadas_avulsas", 0, cat=LpInteger)
        a_cam = LpVariable("camisas_avulsas", 0, cat=LpInteger)

        cost_mistos = lpSum(p["preco"] * x[p["tipo"]] for p in self.catalog["packs_mistos"])
        cost_camisas = lpSum(p["preco"] * y[p["tipo"]] for p in self.catalog["packs_camisas"])
        
        cost_avulso = (
            self.catalog["avulso"]["peca_variada"] * a_var +
            self.catalog["avulso"]["camisa"] * a_cam
        )

        prob += cost_mistos + cost_camisas + cost_avulso

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

        status = prob.solve(solver_name)
        if LpStatus[status] != "Optimal":
            raise RuntimeError(f"Erro no solver: {LpStatus[status]}")

        packs_mistos = {k: int(v.value()) for k, v in x.items() if v.value() > 0}
        packs_camisas = {k: int(v.value()) for k, v in y.items() if v.value() > 0}
        
        avulsos = {
            "peca_variada": int(a_var.value()),
            "camisa": int(a_cam.value()),
        }

        camisas_em_mistos = {k: int(v.value()) for k, v in s.items() if v.value() > 0}

        var_cost = prob.objective.value()
        total_cost = round(fixed_cost + var_cost, 2)

        # Função para converter tipos numpy para tipos nativos serializáveis
        def convert_value(v):
            if isinstance(v, (np.floating, float)):
                return float(round(v, 2))
            if isinstance(v, (np.integer, int)):
                return int(v)
            return v
        
        # Converter todos os valores no breakdown
        detalhe_custos = {
            "custos_fixos": convert_value(fixed_cost),
            "packs_mistos": convert_value(cost_mistos.value()),
            "packs_camisas": convert_value(cost_camisas.value()),
            "itens_avulsos": convert_value(cost_avulso.value()),
            "total_variavel": convert_value(var_cost),
            "total": convert_value(total_cost)
        }

        breakdown = {
            "itens_fixos": {k: convert_value(order[k]) for k in self._SPECIALS if order[k] > 0},
            "packs_mistos": packs_mistos,
            "packs_camisas": packs_camisas,
            "itens_avulsos": avulsos,
            "camisas_em_packs_mistos": camisas_em_mistos,
            "detalhe_custos": detalhe_custos
        }

        return total_cost, breakdown, {v.name: v.value() for v in prob.variables()}

# --------------------------------------------------------------------------- #
#  INTERFACE DE USO
# --------------------------------------------------------------------------- #
def optimizar_pedido(items: Dict[str, int]) -> Tuple[float, Dict[str, Any], Dict[str, Any]]:
    """Função simplificada para otimização direta."""
    return LaundryOptimizer().optimize_order(items)

# --------------------------------------------------------------------------- #
#  HANDLER PARA CHATGPT ACTIONS
# --------------------------------------------------------------------------- #
def gpt_optimize_handler(items: Dict[str, int]) -> Dict[str, Any]:
    """Formata a resposta para o padrão GPT Actions"""
    try:
        total, detalhes, _ = optimizar_pedido(items)
        
        # Função para converter tipos problemáticos recursivamente
        def convert_types(obj):
            if isinstance(obj, (np.floating, float)):
                return float(round(obj, 2))
            if isinstance(obj, (np.integer, int)):
                return int(obj)
            if isinstance(obj, dict):
                return {k: convert_types(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [convert_types(item) for item in obj]
            return obj
        
        return {
            "status": "sucesso",
            "custo_total": round(total, 2),
            "detalhes": convert_types(detalhes)
        }
    except Exception as e:
        return {
            "status": "erro",
            "mensagem": str(e)
        }

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
            "peca_variada": 15,
            "camisa": 8,
            "toalha_ou_lencol": 5,
            "capa_de_edredon": 2
        }
    elif args.json:
        try:
            pedido = json.loads(args.json)
        except json.JSONDecodeError:
            raise ValueError("JSON inválido")
    else:
        parser.error("Use --exemplo ou --json")

    resultado = gpt_optimize_handler(pedido)
    print(json.dumps(resultado, indent=2, ensure_ascii=False))