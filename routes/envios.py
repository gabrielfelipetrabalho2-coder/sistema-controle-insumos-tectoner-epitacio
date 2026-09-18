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
    mes_atual = datetime.now().strftime('%m/%Y')
    
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
            'local': loc, 'total_folhas': t_folhas, 'total_produtos': totais_produtos.get(loc, 0),
            'media': media, 'cor': cor, 'status': status
        })
    resumo_locais = sorted(resumo_locais, key=lambda x: x['local'])
    
    for key, val in envios_ref.items():
        val['id'] = key
        registro_mes = val.get('mes_ref') or (val.get('data', '')[3:10] if len(val.get('data', '')) >= 10 else mes_atual)
                
        if registro_mes == mes_atual:
            local_nome = val.get('local')
            media = int(val.get('media_aplicada', 5000))
            total_acumulado_local = totais_folhas.get(local_nome, 0)
            
            if total_acumulado_local > media:
                val['cor'], val['status'] = 'danger', 'Acima da Média'
            elif total_acumulado_local == media:
                val['cor'], val['status'] = 'warning', 'Na Média'
            else:
                val['cor'], val['status'] = 'success', 'Abaixo da Média'
                
            historico_mes.append(val)
                
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
                        except:
                            quantidade = 0
                
                nome_final = " - ".join(nome_parts) if nome_parts else f"Item {item_id[-4:]}"
                lista_produtos.append({
                    'id': f"{est_id}|{item_id}", 'nome': f"[{est_data.get('nome')}] {nome_final}", 'estoque': quantidade
                })
                
    lista_produtos = sorted(lista_produtos, key=lambda x: x['nome'])
    
    return render_template('index.html', locais=lista_locais, historico=historico_mes, 
                           mes_atual=mes_atual, estoque=estoque_ref, produtos=lista_produtos,
                           resumo_locais=resumo_locais)

@envios_bp.route('/graficos')
def graficos():
    envios_ref = db.reference('envios').get() or {}
    mes_atual = datetime.now().strftime('%m/%Y')
    
    dados_grafico = {}
    dados_grafico_toner = {}
    
    for key, val in envios_ref.items():
        registro_mes = val.get('mes_ref') or (val.get('data', '')[3:10] if len(val.get('data', '')) >= 10 else mes_atual)
        if registro_mes == mes_atual:
            local_nome = val.get('local')
            dados_grafico[local_nome] = dados_grafico.get(local_nome, 0) + int(val.get('folhas', 0))
            dados_grafico_toner[local_nome] = dados_grafico_toner.get(local_nome, 0) + int(val.get('toners', 0))
            
    locais = list(set(list(dados_grafico.keys()) + list(dados_grafico_toner.keys())))
    locais.sort()
    
    folhas_data = [dados_grafico.get(loc, 0) for loc in locais]
    produtos_data = [dados_grafico_toner.get(loc, 0) for loc in locais]
    
    return render_template('graficos.html', locais=locais, folhas=folhas_data, produtos=produtos_data, mes_atual=mes_atual)

@envios_bp.route('/registrar', methods=['POST'])
def registrar():
    local = request.form['local']
    media_input = request.form.get('media')
    
    folhas_str = request.form.get('folhas')
    folhas = int(folhas_str) if folhas_str and folhas_str.strip() else 0
    
    toners_str = request.form.get('toners')
    toners = int(toners_str) if toners_str and toners_str.strip() else 0
    
    produto_composto = request.form.get('produto_id')
    data_input = request.form.get('data')
    
    if folhas < 0 or toners < 0:
        flash('Erro: Valores negativos não são permitidos.', 'danger')
        return redirect('/')
    if folhas == 0 and toners == 0:
        flash('Erro: Você deve enviar Papel, Produto ou Ambos.', 'warning')
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
            
            campo_qtd = next((attr['nome'] for attr in estrutura_data.get('atributos', []) if attr['tipo'] == 'number'), None)
            if not campo_qtd:
                flash('Erro: Estrutura sem coluna numérica!', 'danger')
                return redirect('/')
                
            estoque_prod = int(item_data.get(campo_qtd, 0))
            if toners > estoque_prod:
                flash(f'Bloqueado: Há apenas {estoque_prod} unidades.', 'danger')
                return redirect('/')
                
            item_ref.update({campo_qtd: estoque_prod - toners})
            nome_parts = [str(item_data.get(attr['nome'], '')) for attr in estrutura_data.get('atributos', []) if attr['tipo'] == 'text' and item_data.get(attr['nome'], '')]
            produto_nome_historico = f"[{estrutura_data.get('nome')}] " + " - ".join(nome_parts)
            novo_detalhe = f"{toners}x {produto_nome_historico}"
        except Exception as e:
            flash(f'Erro ao processar item.', 'danger')
            return redirect('/')
            
    elif toners > 0 and not produto_composto:
        flash('Selecione qual Produto está levando!', 'warning')
        return redirect('/')
    
    data_obj = datetime.strptime(data_input, '%Y-%m-%d') if data_input else datetime.now()
    dia_escolhido = data_obj.strftime('%d/%m/%Y')
    mes_ref_registro = data_obj.strftime('%m/%Y')
    
    envios_ref = db.reference('envios')
    todos_envios = envios_ref.get() or {}
    
    media_final = 5000
    if media_input and media_input.strip():
        media_final = int(media_input)
    else:
        ultima_media_local = 5000
        for k, v in todos_envios.items():
            if v.get('local') == local and 'media_aplicada' in v:
                ultima_media_local = int(v['media_aplicada'])
        media_final = ultima_media_local

    estoque_ref.update({'folhas': qtd_estoque_folhas - folhas})
            
    envios_ref.push({
        'local': local, 'folhas': folhas, 'toners': toners,
        'produto_composto': produto_composto, 'produto_nome': produto_nome_historico,
        'detalhes_produtos': novo_detalhe, 'media_aplicada': media_final, 
        'data': dia_escolhido, 'mes_ref': mes_ref_registro
    })
    flash('Sucesso: Saída registrada.', 'success')
    return redirect('/')

@envios_bp.route('/adicionar_estoque', methods=['POST'])
def adicionar_estoque():
    tipo = request.form.get('tipo_material')
    quantidade = int(request.form.get('quantidade_material', 0))
    estoque_atual = db.reference('estoque').get() or {'folhas': 0, 'toners': 0}
    adc = (quantidade * 5000) if tipo == 'caixa_papel' else (quantidade * 500)
    db.reference('estoque').update({'folhas': int(estoque_atual.get('folhas', 0)) + adc})
    flash(f'Estoque de papel atualizado!', 'success')
    return redirect('/')

@envios_bp.route('/editar_estoque', methods=['POST'])
def editar_estoque():
    val = request.form.get('folhas_corretas', '0').strip().replace('.', '').replace(',', '.')
    estoque_atual = db.reference('estoque').get() or {'folhas': 0, 'toners': 0}
    db.reference('estoque').update({'folhas': int(float(val)), 'toners': estoque_atual.get('toners', 0)})
    flash('Sucesso: Valor corrigido!', 'success')
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
                        item_ref.update({campo_qtd: int(item_data.get(campo_qtd, 0)) + toners_devolver})
            except Exception:
                pass
                
    db.reference('envios').child(id).delete()
    flash('Registro deletado e insumos devolvidos.', 'success')
    return redirect('/')

@envios_bp.route('/editar/<id>', methods=['GET', 'POST'])
def editar(id):
    registro_antigo = db.reference('envios').child(id).get()
    if not registro_antigo:
        flash('Registro não encontrado.', 'danger')
        return redirect('/')
        
    if request.method == 'POST':
        # 1. PEGAR OS DADOS DA TELA
        media_input = request.form.get('media')
        media = int(media_input) if media_input and media_input.strip() else int(registro_antigo.get('media_aplicada', 5000))
            
        novas_folhas_str = request.form.get('folhas')
        novas_folhas = int(novas_folhas_str) if novas_folhas_str and novas_folhas_str.strip() else 0
        
        nova_data = request.form.get('data', '')
        if '-' in nova_data:
            try: nova_data = datetime.strptime(nova_data, '%Y-%m-%d').strftime('%d/%m/%Y')
            except: pass
            
        toners_novos_str = request.form.get('toners')
        toners_novos = int(toners_novos_str) if toners_novos_str and toners_novos_str.strip() else 0
        prod_comp_novo = request.form.get('produto_id', "")
        
        # 2. VALIDAÇÃO DE PAPEL
        folhas_antigas = int(registro_antigo.get('folhas', 0))
        estoque_ref = db.reference('estoque')
        estoque_atual = estoque_ref.get() or {'folhas': 0}
        qtd_estoque_folhas = int(estoque_atual.get('folhas', 0))
        
        diferenca_folhas = novas_folhas - folhas_antigas
        if diferenca_folhas > qtd_estoque_folhas:
            flash('Bloqueado: Saldo insuficiente de folhas para correção.', 'danger')
            return redirect(f'/editar/{id}')
            
        # 3. VALIDAÇÃO DE PRODUTO DINÂMICO
        toners_antigos = int(registro_antigo.get('toners', 0))
        prod_comp_antigo = registro_antigo.get('produto_composto', "")
        
        estoque_prod_novo = 0
        campo_qtd_novo = None
        item_ref_novo = None
        nome_historico_novo = ""
        detalhes_produtos_novo = ""
        
        if prod_comp_novo and toners_novos > 0:
            try:
                est_id, item_id = prod_comp_novo.split('|', 1)
                item_ref_novo = db.reference(f'itens_dinamicos/{est_id}/{item_id}')
                item_data_novo = item_ref_novo.get()
                estrutura_data = db.reference(f'estruturas_dinamicas/{est_id}').get()
                
                campo_qtd_novo = next((attr['nome'] for attr in estrutura_data.get('atributos', []) if attr['tipo'] == 'number'), None)
                if campo_qtd_novo and item_data_novo:
                    estoque_prod_novo = int(item_data_novo.get(campo_qtd_novo, 0))
                
                # Checa se o estoque dá conta
                necessidade = toners_novos
                if prod_comp_novo == prod_comp_antigo:
                    necessidade = toners_novos - toners_antigos
                    
                if necessidade > estoque_prod_novo:
                    flash('Bloqueado: Saldo insuficiente do produto selecionado para a correção.', 'danger')
                    return redirect(f'/editar/{id}')
                    
                nome_parts = [str(item_data_novo.get(attr['nome'], '')) for attr in estrutura_data.get('atributos', []) if attr['tipo'] == 'text' and item_data_novo.get(attr['nome'], '')]
                nome_historico_novo = f"[{estrutura_data.get('nome')}] " + " - ".join(nome_parts)
                detalhes_produtos_novo = f"{toners_novos}x {nome_historico_novo}"
            except Exception as e:
                flash('Erro ao ler produto dinâmico.', 'danger')
                return redirect(f'/editar/{id}')

        # 4. APLICA AS ALTERAÇÕES DE FATO
        estoque_ref.update({'folhas': qtd_estoque_folhas - diferenca_folhas})
        
        # Devolve o item antigo pro estoque (se mudou de produto ou zerou)
        if prod_comp_antigo and toners_antigos > 0 and prod_comp_antigo != prod_comp_novo:
            try:
                e_id, i_id = prod_comp_antigo.split('|', 1)
                i_ref = db.reference(f'itens_dinamicos/{e_id}/{i_id}')
                i_data = i_ref.get()
                e_data = db.reference(f'estruturas_dinamicas/{e_id}').get()
                c_qtd = next((attr['nome'] for attr in e_data.get('atributos', []) if attr['tipo'] == 'number'), None)
                if c_qtd and i_data:
                    i_ref.update({c_qtd: int(i_data.get(c_qtd, 0)) + toners_antigos})
            except: pass
                
        # Abate do estoque do item novo
        if prod_comp_novo and toners_novos > 0 and item_ref_novo and campo_qtd_novo:
            if prod_comp_novo == prod_comp_antigo:
                # Se for o mesmo produto, só faz a diferença
                item_ref_novo.update({campo_qtd_novo: estoque_prod_novo - (toners_novos - toners_antigos)})
            else:
                item_ref_novo.update({campo_qtd_novo: estoque_prod_novo - toners_novos})
                
        db.reference('envios').child(id).update({
            'media_aplicada': media, 
            'folhas': novas_folhas, 
            'data': nova_data,
            'toners': toners_novos,
            'produto_composto': prod_comp_novo,
            'produto_nome': nome_historico_novo,
            'detalhes_produtos': detalhes_produtos_novo
        })
        flash('Entrega corrigida e estoque atualizado com sucesso!', 'success')
        return redirect('/')
    else:
        # GET - Tela de carregamento
        data_formatada = ""
        data_orig = registro_antigo.get('data', '')
        if '/' in data_orig:
            try: data_formatada = datetime.strptime(data_orig.split(',')[0].strip(), '%d/%m/%Y').strftime('%Y-%m-%d')
            except: pass
            
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
                            try: quantidade = int(val)
                            except: quantidade = 0
                    nome_final = " - ".join(nome_parts) if nome_parts else f"Item {item_id[-4:]}"
                    lista_produtos.append({
                        'id': f"{est_id}|{item_id}", 'nome': f"[{est_data.get('nome')}] {nome_final}", 'estoque': quantidade
                    })
        lista_produtos = sorted(lista_produtos, key=lambda x: x['nome'])
        
        return render_template('editar.html', registro=registro_antigo, id=id, data_formatada=data_formatada, produtos=lista_produtos)

@envios_bp.route('/novo_local', methods=['GET', 'POST'])
def novo_local():
    if request.method == 'POST':
        nome_local = request.form.get('nome_local', '').strip()
        db.reference('locais_prefeitura').push({'nome': nome_local, 'media_folhas': 5000, 'removivel': True})
        flash(f'Local cadastrado!', 'success')
        return redirect('/')
    return render_template('novo_local.html')

@envios_bp.route('/deletar_local/<id>')
def deletar_local(id):
    db.reference('locais_prefeitura').child(id).delete()
    flash('Local excluído!', 'success')
    return redirect('/')