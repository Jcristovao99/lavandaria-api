from flask import Flask, request, jsonify
from laundry_optimizer_final import optimizar_pedido
import json

app = Flask(__name__)

# Lista de chaves válidas de itens (do CATALOG)
VALID_KEYS = {
    "peca_variada", "camisa", "vestido_simples", "vestido_com_folhos",
    "calca_com_vinco", "blazer", "fronha", "toalha", "lencois",
    "calca_com_blazer", "vestido_cerimonia", "vestido_noiva",
    "casaco_sobretudo", "blusao_almofadado", "blusao_penas"
}

@app.route('/optimize', methods=['POST'])
def optimize():
    # 1) Tenta JSON puro do body
    data = request.get_json(silent=True)
    items = None

    if isinstance(data, dict) and 'items' in data:
        items = data['items']
    elif isinstance(data, dict):
        # Fallback: se todas as chaves no JSON são itens válidos, trata data como items
        if all(k in VALID_KEYS for k in data.keys()):
            items = data

    # 2) Fallback adicional: lê 'items' de query params ou form data
    if items is None:
        raw = request.values.get('items')
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    items = parsed
            except json.JSONDecodeError:
                return jsonify({"erro": "Parâmetro 'items' mal formado JSON."}), 400

    # 3) Validação final
    if not isinstance(items, dict):
        return jsonify({"erro": "Corpo do pedido deve ter o campo 'items' ou JSON direto de itens."}), 400

    # 4) Otimização
    try:
        total, detalhes, _ = optimizar_pedido(items)
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

    return jsonify({"custo_total": total, "detalhes": detalhes})

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
