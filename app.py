from flask import Flask, request, jsonify
import json
import logging
import numpy as np
from flask_cors import CORS
from laundry_optimizer_final import gpt_optimize_handler

app = Flask(__name__)
CORS(app, origins=["https://chat.openai.com"])

# Configuração de logging
logging.basicConfig(level=logging.INFO)
app.logger.setLevel(logging.INFO)

# Lista de chaves válidas de itens (do CATALOG)
VALID_KEYS = {
    "peca_variada", "camisa", "vestido_simples", "vestido_com_folhos",
    "calca_com_vinco", "blazer", "fronha", "toalha", "lencois",
    "calca_com_blazer", "vestido_cerimonia", "vestido_noiva",
    "casaco_sobretudo", "blusao_almofadado", "blusao_penas"
}

@app.route('/optimize', methods=['POST'])
def optimize():
    # 1. Obter e validar dados de entrada
    try:
        app.logger.info("Recebendo solicitação de otimização")
        app.logger.debug(f"Headers: {request.headers}")
        app.logger.debug(f"Body: {request.data.decode('utf-8')}")
        
        # Tentar obter JSON do corpo da requisição
        data = request.get_json(silent=True) or {}
        
        # Aceitar tanto {items: {...}} quanto {...}
        if 'items' in data:
            items = data['items']
        else:
            items = data

        # Validação básica
        if not items or not isinstance(items, dict):
            raise ValueError("Formato inválido: esperado objeto com itens")
            
        # Converter valores para inteiros e validar
        clean_items = {}
        for item, qty in items.items():
            if item not in VALID_KEYS:
                raise ValueError(f"Item desconhecido: '{item}'. Itens válidos: {', '.join(VALID_KEYS)}")
                
            try:
                clean_qty = int(qty)
                if clean_qty < 0:
                    raise ValueError(f"Quantidade negativa para '{item}': {qty}")
                clean_items[item] = clean_qty
            except (TypeError, ValueError):
                raise ValueError(f"Quantidade inválida para '{item}': {qty} - deve ser número inteiro")

        app.logger.info(f"Pedido validado: {clean_items}")

    except Exception as e:
        app.logger.error(f"Erro na validação: {str(e)}")
        return jsonify({
            "status": "erro",
            "mensagem": str(e)
        }), 400

    # 2. Processar otimização usando o handler do ChatGPT
    try:
        app.logger.info("Iniciando otimização...")
        response = gpt_optimize_handler(clean_items)
        app.logger.info("Otimização concluída com sucesso")
        app.logger.debug(f"Resposta: {response}")
        return jsonify(response)

    except Exception as e:
        app.logger.exception("Erro fatal na otimização")
        return jsonify({
            "status": "erro",
            "mensagem": f"Erro interno no servidor: {str(e)}"
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint para verificação de saúde da API"""
    return jsonify({
        "status": "online",
        "versao": "1.0.0",
        "mensagem": "API de otimização de lavanderia operacional"
    })

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 10000))
    app.logger.info(f"Iniciando servidor na porta {port}")
    app.run(host='0.0.0.0', port=port)