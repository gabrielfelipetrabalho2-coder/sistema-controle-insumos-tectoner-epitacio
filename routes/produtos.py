from flask import Blueprint, render_template, request, redirect, flash
from firebase_admin import db

produtos_bp = Blueprint('produtos', __name__)

@produtos_bp.route('/produtos')
def index():
    estruturas_ref = db.reference('estruturas_dinamicas').get() or {}
    lista = []
    for key, val in estruturas_ref.items():
        val['id'] = key
        lista.append(val)
    return render_template('produtos.html', categorias=sorted(lista, key=lambda x: x.get('nome', '')))

@produtos_bp.route('/produtos/cadastro')
def cadastro():
    return render_template('produtos_cadastro.html')

@produtos_bp.route('/produtos/nova', methods=['POST'])
def nova_categoria():
    nome = request.form.get('nome_categoria').strip()
    mostrar_dashboard = request.form.get('mostrar_dashboard')
    nomes_colunas = request.form.getlist('coluna_nome[]')
    tipos_colunas = request.form.getlist('coluna_tipo[]')
    
    if not nome:
        flash('Erro: Nome inválido.', 'danger')
        return redirect('/produtos/cadastro')
        
    atributos = []
    for i in range(len(nomes_colunas)):
        if nomes_colunas[i].strip():
            atributos.append({
                'nome': nomes_colunas[i].strip(),
                'tipo': tipos_colunas[i]
            })
            
    db.reference('estruturas_dinamicas').push({
        'nome': nome,
        'atributos': atributos,
        'mostrar_dashboard': True if mostrar_dashboard else False
    })
    flash(f'Módulo "{nome}" gerado com sucesso! Veja no menu lateral.', 'success')
    return redirect('/produtos')

@produtos_bp.route('/produtos/deletar/<id>')
def deletar_categoria(id):
    # Ao deletar a estrutura, apaga os itens dela também para limpar o banco
    db.reference('estruturas_dinamicas').child(id).delete()
    db.reference(f'itens_dinamicos/{id}').delete()
    flash('Módulo e todos os seus itens foram removidos.', 'success')
    return redirect('/produtos')

@produtos_bp.route('/produtos/editar/<id>', methods=['GET', 'POST'])
def editar_categoria(id):
    if request.method == 'GET':
        estrutura = db.reference(f'estruturas_dinamicas/{id}').get()
        if not estrutura:
            flash('Módulo não encontrado.', 'danger')
            return redirect('/produtos')
        return render_template('produtos_editar.html', estrutura=estrutura, id=id)

    # Lógica de salvar a edição (POST)
    nome = request.form.get('nome_categoria').strip()
    mostrar_dashboard = request.form.get('mostrar_dashboard')
    nomes_colunas = request.form.getlist('coluna_nome[]')
    tipos_colunas = request.form.getlist('coluna_tipo[]')
    nomes_originais = request.form.getlist('coluna_original[]')
    
    atributos = []
    mapa_renomeacao = {}
    
    for i in range(len(nomes_colunas)):
        novo_nome = nomes_colunas[i].strip()
        if novo_nome:
            atributos.append({'nome': novo_nome, 'tipo': tipos_colunas[i]})
            # Se a coluna já existia e mudou de nome, prepara a migração
            if i < len(nomes_originais) and nomes_originais[i]:
                nome_antigo = nomes_originais[i]
                if nome_antigo != novo_nome:
                    mapa_renomeacao[nome_antigo] = novo_nome

    # 1. Salva a estrutura nova no banco
    db.reference(f'estruturas_dinamicas/{id}').update({
        'nome': nome, 
        'atributos': atributos,
        'mostrar_dashboard': True if mostrar_dashboard else False
    })
    
    # 2. Faz a MÁGICA: Renomeia os itens no estoque para acompanharem a nova coluna
    if mapa_renomeacao:
        itens_ref = db.reference(f'itens_dinamicos/{id}')
        itens = itens_ref.get() or {}
        for item_id, item_data in itens.items():
            updates = {}
            for antigo, novo in mapa_renomeacao.items():
                if antigo in item_data:
                    updates[novo] = item_data[antigo] # Passa o valor pro nome novo
                    updates[antigo] = None            # Apaga o nome velho
            if updates:
                itens_ref.child(item_id).update(updates)
                
    flash(f'Estrutura atualizada com sucesso!', 'success')
    return redirect('/produtos')

# ==========================================
# ROTAS DOS MÓDULOS GERADOS DINAMICAMENTE
# ==========================================
@produtos_bp.route('/modulo/<estrutura_id>')
def acessar_modulo(estrutura_id):
    estrutura = db.reference(f'estruturas_dinamicas/{estrutura_id}').get()
    if not estrutura:
        flash('Módulo não encontrado.', 'danger')
        return redirect('/')
        
    itens_ref = db.reference(f'itens_dinamicos/{estrutura_id}').get() or {}
    lista_itens = []
    for key, val in itens_ref.items():
        val['id'] = key
        lista_itens.append(val)
        
    return render_template('modulo_dinamico.html', estrutura=estrutura, estrutura_id=estrutura_id, itens=lista_itens)

@produtos_bp.route('/modulo/<estrutura_id>/novo_item', methods=['POST'])
def novo_item_modulo(estrutura_id):
    dados = {}
    for key, val in request.form.items():
        if val.isdigit():
            dados[key] = int(val)
        else:
            dados[key] = val.strip()
            
    db.reference(f'itens_dinamicos/{estrutura_id}').push(dados)
    flash('Novo item adicionado ao estoque!', 'success')
    return redirect(f'/modulo/{estrutura_id}')
    
@produtos_bp.route('/modulo/<estrutura_id>/deletar/<item_id>')
def deletar_item_modulo(estrutura_id, item_id):
    db.reference(f'itens_dinamicos/{estrutura_id}').child(item_id).delete()
    flash('Item removido.', 'success')
    return redirect(f'/modulo/{estrutura_id}')

@produtos_bp.route('/modulo/<estrutura_id>/editar_item/<item_id>', methods=['POST'])
def editar_item_modulo(estrutura_id, item_id):
    dados = {}
    for key, val in request.form.items():
        if val.isdigit():
            dados[key] = int(val)
        else:
            dados[key] = val.strip()
            
    # Atualiza apenas aquele item específico com os novos valores
    db.reference(f'itens_dinamicos/{estrutura_id}').child(item_id).update(dados)
    flash('Valores do item atualizados com sucesso!', 'success')
    return redirect(f'/modulo/{estrutura_id}')