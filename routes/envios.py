from flask import Blueprint, render_template, request, redirect, flash
from firebase_admin import db
from datetime import datetime

# Criamos o Blueprint (Um "mini app" apenas para envios e estoque)
envios_bp = Blueprint('envios', __name__)

@envios_bp.route('/')
def index():
    locais_ref = db.reference('locais_prefeitura').get() or {}
    envios_ref = db.reference('envios').get() or {}
    estoque_ref = db.reference('estoque').get() or {'folhas': 0, 'toners': 0}
    
    lista_locais = []
    for key, val in locais_ref.items():
        lista_locais.append({
            'id': key,
            'nome': val.get('nome', ''),
            'removivel': val.get('removivel', False)
        })
    lista_locais = sorted(lista_locais, key=lambda x: x['nome'])
    
    historico_mes = []
    dados_grafico = {}
    dados_grafico_toner = {}
    mes_atual = datetime.now().strftime('%m/%Y')
    
    for key, val in envios_ref.items():
        val['id'] = key
        
        registro_mes = val.get('mes_ref')
        if not registro_mes:
            data_str = val.get('data', '')
            if len(data_str) >= 10:
                registro_mes = data_str[3:10]
            else:
                registro_mes = mes_atual
                
        if registro_mes == mes_atual:
            folhas = int(val.get('folhas', 0))
            toners = int(val.get('toners', 0))
            media = int(val.get('media_aplicada', 5000))
            
            if folhas > media:
                val['cor'] = 'danger'
                val['status'] = 'Acima da Média'
            elif folhas == media:
                val['cor'] = 'warning'
                val['status'] = 'Na Média'
            else:
                val['cor'] = 'success'
                val['status'] = 'Abaixo da Média'
                
            historico_mes.append(val)
            
            local_nome = val['local']
            if local_nome in dados_grafico:
                dados_grafico[local_nome] += folhas
                dados_grafico_toner[local_nome] += toners
            else:
                dados_grafico[local_nome] = folhas
                dados_grafico_toner[local_nome] = toners
                
    historico_mes.reverse()
    
    return render_template('index.html', locais=lista_locais, historico=historico_mes, 
                           dados_grafico=dados_grafico, dados_grafico_toner=dados_grafico_toner, 
                           mes_atual=mes_atual, estoque=estoque_ref)

@envios_bp.route('/registrar', methods=['POST'])
def registrar():
    local = request.form['local']
    media_input = request.form.get('media')
    folhas = int(request.form.get('folhas', 0))
    toners = int(request.form.get('toners', 0))
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
    qtd_estoque_toners = int(estoque_atual.get('toners', 0))
    
    if folhas > qtd_estoque_folhas:
        flash(f'Bloqueado: Você tentou enviar {folhas} folhas, mas só há {qtd_estoque_folhas} no estoque.', 'danger')
        return redirect('/')
        
    if toners > qtd_estoque_toners:
        flash(f'Bloqueado: Você tentou enviar {toners} toners, mas só há {qtd_estoque_toners} no estoque.', 'danger')
        return redirect('/')
    
    if data_input:
        data_obj = datetime.strptime(data_input, '%Y-%m-%d')
        dia_escolhido = data_obj.strftime('%d/%m/%Y')
        mes_ref_registro = data_obj.strftime('%m/%Y')
    else:
        dia_escolhido = datetime.now().strftime('%d/%m/%Y')
        mes_ref_registro = datetime.now().strftime('%m/%Y')
    
    envios_ref = db.reference('envios')
    todos_envios = envios_ref.get() or {}
    
    registro_existente_id = None
    registro_existente_dados = None
    
    for key, val in todos_envios.items():
        if val.get('local') == local and val.get('mes_ref') == mes_ref_registro:
            registro_existente_id = key
            registro_existente_dados = val
            break
            
    if media_input and media_input.strip() != "":
        media_final = int(media_input)
    else:
        media_final = int(registro_existente_dados.get('media_aplicada', 5000)) if registro_existente_dados else 5000
            
    estoque_ref.update({
        'folhas': qtd_estoque_folhas - folhas,
        'toners': qtd_estoque_toners - toners
    })
            
    if registro_existente_id:
        folhas_antigas = int(registro_existente_dados.get('folhas', 0))
        toners_antigos = int(registro_existente_dados.get('toners', 0))
        datas_antigas = str(registro_existente_dados.get('data', ''))
        nova_data = f"{datas_antigas}, {dia_escolhido}" if dia_escolhido not in datas_antigas else datas_antigas
        
        envios_ref.child(registro_existente_id).update({
            'folhas': folhas_antigas + folhas, 'toners': toners_antigos + toners,
            'media_aplicada': media_final, 'data': nova_data
        })
        flash(f'Sucesso: Entrega registrada! Estoque atualizado.', 'success')
    else:
        envios_ref.push({
            'local': local, 'folhas': folhas, 'toners': toners,
            'media_aplicada': media_final, 'data': dia_escolhido, 'mes_ref': mes_ref_registro
        })
        flash(f'Sucesso: Primeira entrega do mês registrada e deduzida.', 'success')
        
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
    elif tipo == 'caixa_toner':
        estoque_ref.update({'toners': int(estoque_atual.get('toners', 0)) + (quantidade * 8)})
    elif tipo == 'unidade_toner':
        estoque_ref.update({'toners': int(estoque_atual.get('toners', 0)) + quantidade})
        
    flash(f'Estoque atualizado com sucesso!', 'success')
    return redirect('/')

@envios_bp.route('/editar_estoque', methods=['POST'])
def editar_estoque():
    db.reference('estoque').update({
        'folhas': int(request.form.get('folhas_corretas', 0)),
        'toners': int(request.form.get('toners_corretos', 0))
    })
    flash('Sucesso: Os valores totais do estoque foram corrigidos!', 'success')
    return redirect('/')

@envios_bp.route('/deletar/<id>')
def deletar(id):
    registro = db.reference('envios').child(id).get()
    if registro:
        estoque_atual = db.reference('estoque').get() or {'folhas': 0, 'toners': 0}
        db.reference('estoque').update({
            'folhas': int(estoque_atual.get('folhas', 0)) + int(registro.get('folhas', 0)),
            'toners': int(estoque_atual.get('toners', 0)) + int(registro.get('toners', 0))
        })
    db.reference('envios').child(id).delete()
    flash('Registro deletado e insumos devolvidos ao estoque principal!', 'success')
    return redirect('/')

# A edição permanece 100% blindada conforme combinamos
@envios_bp.route('/editar/<id>', methods=['GET', 'POST'])
def editar(id):
    if request.method == 'POST':
        media = int(request.form.get('media', 5000))
        novas_folhas = int(request.form.get('folhas', 0))
        novos_toners = int(request.form.get('toners', 0))
        datas_editadas = request.form.get('datas_historico', '')
        
        registro_antigo = db.reference('envios').child(id).get()
        folhas_antigas = int(registro_antigo.get('folhas', 0))
        toners_antigos = int(registro_antigo.get('toners', 0))
        
        estoque_ref = db.reference('estoque')
        estoque_atual = estoque_ref.get() or {'folhas': 0, 'toners': 0}
        qtd_estoque_folhas = int(estoque_atual.get('folhas', 0))
        qtd_estoque_toners = int(estoque_atual.get('toners', 0))
        
        diferenca_folhas = novas_folhas - folhas_antigas
        diferenca_toners = novos_toners - toners_antigos
        
        if diferenca_folhas > qtd_estoque_folhas or diferenca_toners > qtd_estoque_toners:
            flash(f'Bloqueado na Edição: Estoque insuficiente para realizar este aumento!', 'danger')
            return redirect(f'/editar/{id}')
            
        estoque_ref.update({'folhas': qtd_estoque_folhas - diferenca_folhas, 'toners': qtd_estoque_toners - diferenca_toners})
        db.reference('envios').child(id).update({
            'media_aplicada': media, 'folhas': novas_folhas, 'toners': novos_toners, 'data': datas_editadas
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