from flask import Flask, request, jsonify, send_file, redirect, url_for
from laundry_optimizer_final import gpt_optimize_handler, CATALOG
from reportlab.lib.pagesizes import A5
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.units import cm
from datetime import datetime
import tempfile
import logging
import os
import uuid
from flask_cors import CORS
import threading
import time

app = Flask(__name__)
CORS(app, origins=["https://chat.openai.com"])

# Configurações da empresa
LOGO_URL = os.environ.get('LOGO_URL', 'https://i.imgur.com/neLsj8d.png')
TELEFONE = os.environ.get('TELEFONE', '910191078')

# Configuração de logging
logging.basicConfig(level=logging.INFO)
app.logger.setLevel(logging.INFO)

# Lista de chaves válidas
VALID_KEYS = {
    "peca_variada", "camisa", "vestido_simples",
    "calca_com_vinco", "blazer", "toalha_ou_lencol",
    "capa_de_edredon", "calca_com_blazer", "vestido_cerimonia", 
    "vestido_noiva", "casaco_sobretudo", "blusao_almofadado", "blusao_penas"
}

# Cache para armazenar resultados temporariamente
result_cache = {}
cache_lock = threading.Lock()

# ========================================================================== #
#  LIMPEZA AUTOMÁTICA DO CACHE (executa a cada 5 minutos)
# ========================================================================== #
def clean_cache():
    while True:
        time.sleep(300)  # 5 minutos
        now = time.time()
        with cache_lock:
            global result_cache
            result_cache = {k: v for k, v in result_cache.items() if now - v['timestamp'] < 1800}  # Mantém por 30 min

# Inicia thread de limpeza
cache_cleaner = threading.Thread(target=clean_cache, daemon=True)
cache_cleaner.start()

# ========================================================================== #
#  GERADOR DE PDF PROFISSIONAL
# ========================================================================== #
def generate_receipt_pdf(resultado):
    """Gera PDF profissional com design idêntico ao fornecido"""
    try:
        # Configurações
        width, height = A5
        margin = 1*cm
        styles = getSampleStyleSheet()
        
        # Criar arquivo temporário
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmpfile:
            filename = tmpfile.name
            c = canvas.Canvas(filename, pagesize=A5)
            
            # Estilos personalizados
            item_style = ParagraphStyle(
                'item',
                parent=styles['BodyText'],
                fontName='Helvetica',
                fontSize=12,
                leading=14,
                textColor=colors.HexColor('#182232')
            )
            
            total_style = ParagraphStyle(
                'total',
                parent=styles['BodyText'],
                fontName='Helvetica-Bold',
                fontSize=14,
                leading=16,
                textColor=colors.HexColor('#1a2d44')
            )
            
            phone_style = ParagraphStyle(
                'phone',
                parent=styles['BodyText'],
                fontName='Helvetica-Bold',
                fontSize=14,
                leading=16,
                alignment=1,
                textColor=colors.HexColor('#1a2d44'),
                spaceBefore=20
            )
            
            # Fundo
            c.setFillColor(colors.HexColor('#f9f9f7'))
            c.rect(0, 0, width, height, fill=1, stroke=0)
            
            # Logo centralizada (já inclui o nome da empresa)
            try:
                logo = ImageReader(LOGO_URL)
                c.drawImage(logo, width/2-55, height-140, width=110, height=110, 
                            preserveAspectRatio=True, mask='auto')
            except Exception as e:
                app.logger.error(f"Erro ao carregar logo: {str(e)}")
            
            # Linha divisória abaixo do logo
            c.setStrokeColor(colors.HexColor('#192844'))
            c.setLineWidth(2)
            c.line(margin, height-160, width-margin, height-160)
            
            # Tabela de itens
            data = [['Descrição', 'Quantidade/Preço', 'Subtotal']]
            
            # Adicionar itens fixos
            for item, qty in resultado['detalhes']['itens_fixos'].items():
                preco = CATALOG['avulso'][item]
                desc = item.replace('_', ' ').replace('ou', '/').title()
                data.append([
                    Paragraph(desc, item_style),
                    f"{qty} × €{preco:.2f}".replace('.', ','),
                    f"€ {qty*preco:.2f}".replace('.', ',')
                ])
            
            # Adicionar packs mistos
            for pack, qty in resultado['detalhes']['packs_mistos'].items():
                pack_data = next(p for p in CATALOG['packs_mistos'] if p['tipo'] == pack)
                data.append([
                    Paragraph(f"Pack Misto {pack} peças", item_style),
                    f"{qty} × €{pack_data['preco']:.2f}".replace('.', ','),
                    f"€ {qty*pack_data['preco']:.2f}".replace('.', ',')
                ])
            
            # Adicionar packs de camisas
            for pack, qty in resultado['detalhes']['packs_camisas'].items():
                pack_data = next(p for p in CATALOG['packs_camisas'] if p['tipo'] == pack)
                data.append([
                    Paragraph(f"Pack Camisas {pack}", item_style),
                    f"{qty} × €{pack_data['preco']:.2f}".replace('.', ','),
                    f"€ {qty*pack_data['preco']:.2f}".replace('.', ',')
                ])
            
            # Adicionar itens avulsos
            for item, qty in resultado['detalhes']['itens_avulsos'].items():
                if qty > 0:
                    preco = CATALOG['avulso'][item]
                    desc = item.replace('_', ' ').title()
                    data.append([
                        Paragraph(desc, item_style),
                        f"{qty} × €{preco:.2f}".replace('.', ','),
                        f"€ {qty*preco:.2f}".replace('.', ',')
                    ])
            
            # Criar tabela
            table = Table(data, colWidths=[width*0.45, width*0.25, width*0.2])
            table.setStyle(TableStyle([
                ('FONT', (0,0), (-1,0), 'Helvetica-Bold', 12),
                ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('LINEABOVE', (0,0), (-1,0), 1, colors.HexColor('#192844')),
                ('LINEBELOW', (0,0), (-1,0), 1, colors.HexColor('#192844')),
                ('LINEABOVE', (0,-1), (-1,-1), 0.5, colors.lightgrey),
                ('PADDING', (0,0), (-1,-1), 6),
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f0f0f0')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#1a2d44'))
            ]))
            
            # Desenhar tabela
            table.wrapOn(c, width-2*margin, height)
            table.drawOn(c, margin, height-320)
            
            # Linha divisória final
            c.setStrokeColor(colors.HexColor('#192844'))
            c.setLineWidth(2)
            c.line(margin, height-400, width-margin, height-400)
            
            # Total geral
            total_text = f"€ {resultado['custo_total']:.2f}".replace('.', ',')
            total_para = Paragraph("<b>TOTAL</b>", total_style)
            total_para.wrapOn(c, width-2*margin, height)
            total_para.drawOn(c, margin, height-430)
            
            total_val = Paragraph(f"<b>{total_text}</b>", total_style)
            total_val.wrapOn(c, width-2*margin, height)
            total_val.drawOn(c, width-margin-100, height-430)
            
            # Telefone
            phone_para = Paragraph(f"<b>{TELEFONE}</b>", phone_style)
            phone_para.wrapOn(c, width-2*margin, height)
            phone_para.drawOn(c, margin, 1*cm)
            
            c.save()
            return filename
            
    except Exception as e:
        app.logger.error(f"Erro ao gerar PDF: {str(e)}")
        raise

# ========================================================================== #
#  ENDPOINTS DA API
# ========================================================================== #
@app.route('/optimize', methods=['POST'])
def optimize():
    # 1. Obter e validar dados de entrada
    try:
        app.logger.info("Recebendo solicitação de otimização")
        
        # Tentar obter JSON do corpo da requisição
        data = request.get_json(silent=True) or {}
        
        # Aceitar tanto o formato direto (novo) quanto o formato com "items" (antigo)
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
        
        # Gerar ID único para o resultado
        receipt_id = str(uuid.uuid4())
        
        # Armazenar resultado no cache
        with cache_lock:
            result_cache[receipt_id] = {
                "result": response,
                "timestamp": time.time()
            }
        
        # Adicionar URL para download do PDF (GET)
        base_url = os.environ.get('BASE_URL', 'https://lavanderia-optimizer.onrender.com')
        response['pdf_url'] = f"{base_url}/download_pdf/{receipt_id}"
        
        app.logger.info("Otimização concluída com sucesso")
        return jsonify(response)

    except Exception as e:
        app.logger.exception("Erro fatal na otimização")
        return jsonify({
            "status": "erro",
            "mensagem": f"Erro interno no servidor: {str(e)}"
        }), 500

@app.route('/download_pdf/<receipt_id>', methods=['GET'])
def download_pdf(receipt_id):
    """Endpoint GET para download direto do PDF"""
    try:
        # Recuperar resultado do cache
        with cache_lock:
            if receipt_id not in result_cache:
                return jsonify({
                    "status": "erro",
                    "mensagem": "Recibo expirado ou inválido"
                }), 404
                
            resultado = result_cache[receipt_id]["result"]
        
        # Gerar PDF
        filename = generate_receipt_pdf(resultado)
        
        return send_file(
            filename,
            as_attachment=True,
            download_name=f"recibo_engomadoria_teresa_{datetime.now().strftime('%Y%m%d')}.pdf",
            mimetype='application/pdf'
        )
            
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint para verificação de saúde da API"""
    return jsonify({
        "status": "online",
        "versao": "1.2.0",
        "mensagem": "API com suporte a download de PDF via GET"
    })

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 10000))
    app.logger.info(f"Iniciando servidor na porta {port}")
    app.run(host='0.0.0.0', port=port)