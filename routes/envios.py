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
    
    # --- OPÇÃO 1: Calcula os TOTAIS EXATOS POR LOCAL ---
    totais_folhas = {}
    totais_produtos = {}
    medias_locais = {}
    
    for key, val in envios_ref.items():
        registro_mes = val.get('mes_ref') or (val.get('data', '')[3:10] if len(val.get('data', '')) >= 10 else mes_atual)
        if registro_mes == mes_atual:
            local_nome = val.get('local')
            totais_folhas[local_nome] = totais_folhas.get(local_nome, 0) + int(val.get('folhas', 0))
            totais_produtos[local_nome] = totais_produtos.get(local_nome, 0) + int(val.get('toners', 0))
            medias_locais[local_nome] = int(val.get('media_aplicada', 5000))
            
    # Cria a lista de resumo para o HTML
    resumo_locais = []
    for loc, t_folhas in totais_folhas.items():
        media = medias_locais.get(loc, 5000)
        if t_folhas > media:
            cor, status = 'danger', 'Acima da Média'
        elif t_folhas == media:
            cor, status = 'warning', 'Na Média'
        else:
            cor, status = 'success', 'Abaixo da Média'
            
        resumo_locais.append({
            'local': loc,
            'total_folhas': t_folhas,
            'total_produtos': totais_produtos.get(loc, 0),
            'media': media,
            'cor': cor,
            'status': status
        })
    resumo_locais = sorted(resumo_locais, key=lambda x: x['local'])
    
    # Constrói a tabela Extrato
    for key, val in envios_ref.items():
        val['id'] = key
        registro_mes = val.get('mes_ref') or (val.get('data', '')[3:10] if len(val.get('data', '')) >= 10 else mes_atual)
                
        if registro_mes == mes_atual:
            local_nome = val.get('local')
            folhas = int(val.get('folhas', 0))
            toners = int(val.get('toners', 0))
            media = int(val.get('media_aplicada', 5000))
            
            total_acumulado_local = totais_folhas.get(local_nome, 0)
            
            if total_acumulado_local > media:
                val['cor'], val['status'] = 'danger', 'Acima da Média'
            elif total_acumulado_local == media:
                val['cor'], val['status'] = 'warning', 'Na Média'
            else:
                val['cor'], val['status'] = 'success', 'Abaixo da Média'
                
            historico_mes.append(val)
            dados_grafico[local_nome] = dados_grafico.get(local_nome, 0) + folhas
            dados_grafico_toner[local_nome] = dados_grafico_toner.get(local_nome, 0) + toners
                
    historico_mes.reverse()
    
    estruturas_ref = db.reference('estruturas_dinamicas').get() or {}
    lista_produtos = []
    
    for est_id, est_data in estruturas_ref.items():
        if est_data.get('mostrar_dashboard'):
            itens_ref = db.reference(f'itens_dinamicos/{est_id}').get() or {}
            for item_id, item_data in itens_ref.items():
                nome_parts = []
                quantidade = 0
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
                    'id': f"{est_id}|{item_id}",
                    'nome': f"[{est_data.get('nome')}] {nome_final}",
                    'estoque': quantidade
                })
                
    lista_produtos = sorted(lista_produtos, key=lambda x: x['nome'])
    
    return render_template('index.html', locais=lista_locais, historico=historico_mes, 
                           dados_grafico=dados_grafico, dados_grafico_toner=dados_grafico_toner, 
                           mes_atual=mes_atual, estoque=estoque_ref, produtos=lista_produtos,
                           resumo_locais=resumo_locais)

@envios_bp.route('/registrar', methods=['POST'])
def registrar():
    local = request.form['local']
    media_input = request.form.get('media')
    folhas = int(request.form.get('folhas', 0))
    toners = int(request.form.get('toners', 0))
    produto_composto = request.form.get('produto_id')
    data_input = request.form.get('data')
    
    if folhas < 0 or toners < 0:
        flash('Erro: Valores negativos não são permitidos.', 'danger')
        return redirect('/')
    if folhas == 0 and toners == 0:
        flash('Erro: Você deve registrar o envio de material.', 'danger')
        return redirect('/')

    estoque_ref = db.reference('estoque')
    estoque_atual = estoque_ref.get() or {'folhas': 0, 'toners': 0}
    qtd_estoque_folhas = int(estoque_atual.get('folhas', 0))
    
    if folhas > qtd_estoque_folhas:
        flash(f'Bloqueado: Você tentou enviar {folhas} folhas, mas só há {qtd_estoque_folhas} no estoque.', 'danger')
        return redirect('/')
        
    produto_nome_historico = ""
    novo_detalhe = ""
    
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
                flash('Erro: Esta estrutura não tem uma coluna de Número para abater o estoque!', 'danger')
                return redirect('/')
                
            estoque_prod = int(item_data.get(campo_qtd, 0))
            if toners > estoque_prod:
                flash(f'Bloqueado: Há apenas {estoque_prod} unidades deste item em estoque.', 'danger')
                return redirect('/')
                
            item_ref.update({campo_qtd: estoque_prod - toners})
            produto_nome_historico = f"[{estrutura_data.get('nome')}] " + " - ".join(nome_parts)
            novo_detalhe = f"{toners}x {produto_nome_historico}"
            
        except Exception as e:
            flash(f'Erro ao processar item: {str(e)}', 'danger')
            return redirect('/')
            
    elif toners > 0 and not produto_composto:
        flash('Bloqueado: Você informou a quantidade, mas não selecionou o Produto na lista!', 'warning')
        return redirect('/')
    
    data_obj = datetime.strptime(data_input, '%Y-%m-%d') if data_input else datetime.now()
    dia_escolhido = data_obj.strftime('%d/%m/%Y')
    mes_ref_registro = data_obj.strftime('%m/%Y')
    
    envios_ref = db.reference('envios')
    media_final = int(media_input) if media_input and media_input.strip() else 5000
    estoque_ref.update({'folhas': qtd_estoque_folhas - folhas})
            
    envios_ref.push({
        'local': local, 
        'folhas': folhas, 
        'toners': toners,
        'produto_composto': produto_composto,
        'produto_nome': produto_nome_historico,
        'detalhes_produtos': novo_detalhe,
        'media_aplicada': media_final, 
        'data': dia_escolhido, 
        'mes_ref': mes_ref_registro
    })
    flash('Sucesso: Saída de insumos registrada com sucesso!', 'success')
        
    return redirect('/')

@envios_bp.route('/adicionar_estoque', methods=['POST'])
def adicionar_estoque():
    tipo = request.form.get('tipo_material')
    quantidade = int(request.form.get('quantidade_material', 0))
    estoque_ref = db.reference('estoque')
    estoque_atual = estoque_ref.get() or {'folhas': 0, 'toners': 0}
    
    if tipo == 'caixa_papel':
        estoque_ref.update({'folhas': int(estoque_atual.get('folhas', 0)) + (quantidade * 5000)})
    elif tipo == 'resma_papel':
        estoque_ref.update({'folhas': int(estoque_atual.get('folhas', 0)) + (quantidade * 500)})
        
    flash(f'Estoque de papel atualizado com sucesso!', 'success')
    return redirect('/')

@envios_bp.route('/editar_estoque', methods=['POST'])
def editar_estoque():
    def limpar_numero(valor):
        if not valor: return 0
        valor_str = str(valor).strip().replace('.', '').replace(',', '.')
        try:
            return int(float(valor_str))
        except ValueError:
            return 0

    estoque_atual = db.reference('estoque').get() or {'folhas': 0, 'toners': 0}
    dados = {
        'folhas': limpar_numero(request.form.get('folhas_corretas')),
        'toners': estoque_atual.get('toners', 0)
    }
    
    db.reference('estoque').update(dados)
    flash('Sucesso: O valor total de folhas foi corrigido!', 'success')
    return redirect('/')

@envios_bp.route('/deletar/<id>')
def deletar(id):
    registro = db.reference('envios').child(id).get()
    if registro:
        estoque_atual = db.reference('estoque').get() or {'folhas': 0, 'toners': 0}
        db.reference('estoque').update({'folhas': int(estoque_atual.get('folhas', 0)) + int(registro.get('folhas', 0))})
        
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