from flask import Flask, request, jsonify
from laundry_optimizer_final import optimizar_pedido
import json

app = Flask(__name__)

@app.route('/optimize', methods=['POST'])
def optimize():
    # 1) Tenta ler JSON puro do body
    data = request.get_json(silent=True)
    items = None

    if isinstance(data, dict) and 'items' in data:
        items = data['items']
    else:
        # 2) Fallback: lê 'items' de query params ou form data
        raw = request.values.get('items')
        if raw:
            try:
                items = json.loads(raw)
            except json.JSONDecodeError:
                return jsonify({"erro": "Parametro 'items' está mal formado JSON."}), 400

    # 3) Validação final
    if not isinstance(items, dict):
        return jsonify({"erro": "Corpo do pedido deve ter o campo 'items' como objeto JSON."}), 400

    # 4) Calcular orçamento
    try:
        total, detalhes, _ = optimizar_pedido(items)
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

    return jsonify({"custo_total": total, "detalhes": detalhes})

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
