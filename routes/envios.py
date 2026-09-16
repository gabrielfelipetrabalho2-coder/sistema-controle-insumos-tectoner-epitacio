from flask import Blueprint, render_template, request, redirect, flash
from firebase_admin import db
from datetime import datetime

envios_bp = Blueprint('envios', __name__)

@envios_bp.route('/')
def index():
    locais_ref = db.reference('locais_prefeitura').get() or {}
    envios_ref = db.reference('envios').get() or {}
    estoque_ref = db.reference('estoque').get() or {'folhas': 0, 'toners': 0}
    
    lista_locais = [{'id': k, 'nome': v.get('nome', ''), 'removivel': v.get('removivel', False)} for k, v in locais_ref.items()]
    lista_locais = sorted(lista_locais, key=lambda x: x['nome'])
    
    historico_mes = []
    dados_grafico = {}
    dados_grafico_toner = {}
    mes_atual = datetime.now().strftime('%m/%Y')
    
    for key, val in envios_ref.items():
        val['id'] = key
        registro_mes = val.get('mes_ref') or (val.get('data', '')[3:10] if len(val.get('data', '')) >= 10 else mes_atual)
                
        if registro_mes == mes_atual:
            folhas = int(val.get('folhas', 0))
            toners = int(val.get('toners', 0))
            media = int(val.get('media_aplicada', 5000))
            
            if folhas > media:
                val['cor'], val['status'] = 'danger', 'Acima da Média'
            elif folhas == media:
                val['cor'], val['status'] = 'warning', 'Na Média'
            else:
                val['cor'], val['status'] = 'success', 'Abaixo da Média'
                
            historico_mes.append(val)
            
            local_nome = val['local']
            dados_grafico[local_nome] = dados_grafico.get(local_nome, 0) + folhas
            dados_grafico_toner[local_nome] = dados_grafico_toner.get(local_nome, 0) + toners
                
    historico_mes.reverse()
    
    # --- LEITURA DINÂMICA DO NOVO ERP ---
    estruturas_ref = db.reference('estruturas_dinamicas').get() or {}
    lista_produtos = []
    
    for est_id, est_data in estruturas_ref.items():
        if est_data.get('mostrar_dashboard'):
            itens_ref = db.reference(f'itens_dinamicos/{est_id}').get() or {}
            for item_id, item_data in itens_ref.items():
                nome_parts = []
                quantidade = 0
                # O sistema varre as colunas que você inventou para montar a lista
                for attr in est_data.get('atributos', []):
                    val = item_data.get(attr['nome'], '')
                    if attr['tipo'] == 'text' and val:
                        nome_parts.append(str(val))
                    elif attr['tipo'] == 'number' and quantidade == 0:
                        try:
                            quantidade = int(val)
                        except (ValueError, TypeError):
                            quantidade = 0
                
                nome_final = " - ".join(nome_parts) if nome_parts else f"Item {item_id[-4:]}"
                
                lista_produtos.append({
                    'id': f"{est_id}|{item_id}", # Código composto para o sistema achar o item depois
                    'nome': f"[{est_data.get('nome')}] {nome_final}",
                    'estoque': quantidade
                })
                
    lista_produtos = sorted(lista_produtos, key=lambda x: x['nome'])
    
    return render_template('index.html', locais=lista_locais, historico=historico_mes, 
                           dados_grafico=dados_grafico, dados_grafico_toner=dados_grafico_toner, 
                           mes_atual=mes_atual, estoque=estoque_ref, produtos=lista_produtos)

@envios_bp.route('/registrar', methods=['POST'])
def registrar():
    local = request.form['local']
    media_input = request.form.get('media')
    folhas = int(request.form.get('folhas', 0))
    toners = int(request.form.get('toners', 0))
    produto_composto = request.form.get('produto_id') # Recebe "estrutura_id|item_id"
    data_input = request.form.get('data')
    
    if folhas < 0 or toners < 0:
        flash('Erro: Valores negativos não são permitidos.', 'danger')
        return redirect('/')
    if folhas == 0 and toners == 0:
        flash('Erro: Você deve registrar o envio de material.', 'danger')
        return redirect('/')

    # Valida Papel
    estoque_ref = db.reference('estoque')
    estoque_atual = estoque_ref.get() or {'folhas': 0, 'toners': 0}
    qtd_estoque_folhas = int(estoque_atual.get('folhas', 0))
    if folhas > qtd_estoque_folhas:
        flash(f'Bloqueado: Você tentou enviar {folhas} folhas, mas só há {qtd_estoque_folhas} no estoque.', 'danger')
        return redirect('/')
        
    # Valida e Desconta o Produto Dinâmico
    produto_nome_historico = ""
    if produto_composto and toners > 0:
        try:
            est_id, item_id = produto_composto.split('|', 1)
            item_ref = db.reference(f'itens_dinamicos/{est_id}/{item_id}')
            item_data = item_ref.get()
            estrutura_data = db.reference(f'estruturas_dinamicas/{est_id}').get()
            
            campo_qtd = None
            nome_parts = []
            for attr in estrutura_data.get('atributos', []):
                if attr['tipo'] == 'number' and not campo_qtd:
                    campo_qtd = attr['nome']
                elif attr['tipo'] == 'text':
                    val = item_data.get(attr['nome'], '')
                    if val: nome_parts.append(str(val))
                    
            if not campo_qtd:
                flash('Erro: Esta estrutura não tem uma coluna de Número para dar baixa!', 'danger')
                return redirect('/')
                
            estoque_prod = int(item_data.get(campo_qtd, 0))
            if toners > estoque_prod:
                flash(f'Bloqueado: Há apenas {estoque_prod} unidades deste item em estoque.', 'danger')
                return redirect('/')
                
            # Atualiza no banco
            item_ref.update({campo_qtd: estoque_prod - toners})
            produto_nome_historico = f"[{estrutura_data.get('nome')}] " + " - ".join(nome_parts)
            
        except Exception as e:
            flash(f'Erro ao processar item: {str(e)}', 'danger')
            return redirect('/')
            
    elif toners > 0 and not produto_composto:
        flash('Bloqueado: Você informou a quantidade, mas não selecionou o Produto na lista!', 'warning')
        return redirect('/')
    
    # Tratamento de Datas
    data_obj = datetime.strptime(data_input, '%Y-%m-%d') if data_input else datetime.now()
    dia_escolhido = data_obj.strftime('%d/%m/%Y')
    mes_ref_registro = data_obj.strftime('%m/%Y')
    
    envios_ref = db.reference('envios')
    todos_envios = envios_ref.get() or {}
    
    registro_existente_id = None
    registro_existente_dados = None
    for key, val in todos_envios.items():
        if val.get('local') == local and val.get('mes_ref') == mes_ref_registro:
            registro_existente_id = key
            registro_existente_dados = val
            break
            
    media_final = int(media_input) if media_input and media_input.strip() else int(registro_existente_dados.get('media_aplicada', 5000)) if registro_existente_dados else 5000
            
    estoque_ref.update({'folhas': qtd_estoque_folhas - folhas})
            
    if registro_existente_id:
        folhas_antigas = int(registro_existente_dados.get('folhas', 0))
        toners_antigos = int(registro_existente_dados.get('toners', 0))
        datas_antigas = str(registro_existente_dados.get('data', ''))
        nova_data = f"{datas_antigas}, {dia_escolhido}" if dia_escolhido not in datas_antigas else datas_antigas
        
        envios_ref.child(registro_existente_id).update({
            'folhas': folhas_antigas + folhas, 
            'toners': toners_antigos + toners,
            'produto_composto': produto_composto,
            'produto_nome': produto_nome_historico,
            'media_aplicada': media_final, 'data': nova_data
        })
        flash('Sucesso: Entrega registrada e baixada do estoque!', 'success')
    else:
        envios_ref.push({
            'local': local, 'folhas': folhas, 'toners': toners,
            'produto_composto': produto_composto,
            'produto_nome': produto_nome_historico,
            'media_aplicada': media_final, 'data': dia_escolhido, 'mes_ref': mes_ref_registro
        })
        flash('Sucesso: Primeira entrega do mês registrada!', 'success')
        
    return redirect('/')

@envios_bp.route('/deletar/<id>')
def deletar(id):
    registro = db.reference('envios').child(id).get()
    if registro:
        estoque_atual = db.reference('estoque').get() or {'folhas': 0, 'toners': 0}
        db.reference('estoque').update({'folhas': int(estoque_atual.get('folhas', 0)) + int(registro.get('folhas', 0))})
        
        # Devolve o insumo para a estrutura dinâmica, se existir
        produto_composto = registro.get('produto_composto')
        toners_devolver = int(registro.get('toners', 0))
        
        if produto_composto and toners_devolver > 0:
            try:
                est_id, item_id = produto_composto.split('|', 1)
                item_ref = db.reference(f'itens_dinamicos/{est_id}/{item_id}')
                item_data = item_ref.get()
                estrutura_data = db.reference(f'estruturas_dinamicas/{est_id}').get()
                
                if item_data and estrutura_data:
                    campo_qtd = next((attr['nome'] for attr in estrutura_data.get('atributos', []) if attr['tipo'] == 'number'), None)
                    if campo_qtd:
                        estoque_prod = int(item_data.get(campo_qtd, 0))
                        item_ref.update({campo_qtd: estoque_prod + toners_devolver})
            except Exception:
                pass
                
    db.reference('envios').child(id).delete()
    flash('Registro deletado e insumos devolvidos ao estoque!', 'success')
    return redirect('/')

@envios_bp.route('/editar/<id>', methods=['GET', 'POST'])
def editar(id):
    if request.method == 'POST':
        media = int(request.form.get('media', 5000))
        novas_folhas = int(request.form.get('folhas', 0))
        datas_editadas = request.form.get('datas_historico', '')
        
        registro_antigo = db.reference('envios').child(id).get()
        folhas_antigas = int(registro_antigo.get('folhas', 0))
        
        estoque_ref = db.reference('estoque')
        estoque_atual = estoque_ref.get() or {'folhas': 0, 'toners': 0}
        qtd_estoque_folhas = int(estoque_atual.get('folhas', 0))
        
        diferenca_folhas = novas_folhas - folhas_antigas
        if diferenca_folhas > qtd_estoque_folhas:
            flash(f'Bloqueado: Estoque insuficiente para realizar este aumento!', 'danger')
            return redirect(f'/editar/{id}')
            
        estoque_ref.update({'folhas': qtd_estoque_folhas - diferenca_folhas})
        db.reference('envios').child(id).update({
            'media_aplicada': media, 'folhas': novas_folhas, 'data': datas_editadas
        })
        flash('Registro corrigido!', 'success')
        return redirect('/')
    else:
        registro = db.reference('envios').child(id).get()
        estoque_atual = db.reference('estoque').get() or {'folhas': 0, 'toners': 0}
        return render_template('editar.html', registro=registro, id=id, estoque=estoque_atual)

@envios_bp.route('/novo_local', methods=['GET', 'POST'])
def novo_local():
    if request.method == 'POST':
        nome_local = request.form.get('nome_local', '').strip()
        db.reference('locais_prefeitura').push({'nome': nome_local, 'media_folhas': 5000, 'removivel': True})
        flash(f'Sucesso: O novo local "{nome_local}" foi cadastrado!', 'success')
        return redirect('/')
    return render_template('novo_local.html')

@envios_bp.route('/deletar_local/<id>')
def deletar_local(id):
    db.reference('locais_prefeitura').child(id).delete()
    flash('Local customizado excluído permanentemente!', 'success')
    return redirect('/')