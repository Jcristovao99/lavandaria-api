from flask import Flask, request, jsonify
from laundry_optimizer_final import optimizar_pedido

app = Flask(__name__)

@app.route('/optimize', methods=['POST'])
def optimize():
    data = request.get_json()
    items = data["items"]
    total, detalhes, _ = optimizar_pedido(items)
    return jsonify({"custo_total": total, "detalhes": detalhes})

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
