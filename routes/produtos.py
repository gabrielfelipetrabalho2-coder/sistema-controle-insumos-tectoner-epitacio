from flask import Blueprint, render_template, request, redirect, flash
from firebase_admin import db

produtos_bp = Blueprint('produtos', __name__)

@produtos_bp.route('/produtos')
def index():
    categorias_ref = db.reference('categorias_produtos').get() or {}
    
    lista_categorias = []
    for key, val in categorias_ref.items():
        val['id'] = key
        lista_categorias.append(val)
        
    lista_categorias = sorted(lista_categorias, key=lambda x: x.get('nome', ''))
    
    return render_template('produtos.html', categorias=lista_categorias)

@produtos_bp.route('/produtos/nova', methods=['POST'])
def nova_categoria():
    nome = request.form.get('nome_categoria').strip()
    # Pega as listas de nomes e tipos que vieram do HTML
    nomes_colunas = request.form.getlist('coluna_nome[]')
    tipos_colunas = request.form.getlist('coluna_tipo[]')
    
    if not nome:
        flash('Erro: O nome da categoria/produto não pode ser vazio.', 'danger')
        return redirect('/produtos')
        
    # Monta um dicionário com cada atributo e seu respectivo tipo
    atributos = []
    for i in range(len(nomes_colunas)):
        if nomes_colunas[i].strip():
            atributos.append({
                'nome': nomes_colunas[i].strip(),
                'tipo': tipos_colunas[i]
            })
            
    db.reference('categorias_produtos').push({
        'nome': nome,
        'atributos': atributos,
        'estoque_total': 0
    })
    
    flash(f'Sucesso: Produto/Categoria "{nome}" criada com estrutura customizada!', 'success')
    return redirect('/produtos')

@produtos_bp.route('/produtos/deletar/<id>')
def deletar_categoria(id):
    categoria = db.reference('categorias_produtos').child(id).get()
    
    if not categoria:
        flash('Erro: Categoria não encontrada.', 'danger')
        return redirect('/produtos')
        
    if int(categoria.get('estoque_total', 0)) > 0:
        flash('Bloqueado: Você não pode deletar essa categoria pois ainda há itens no estoque dela!', 'danger')
        return redirect('/produtos')
        
    db.reference('categorias_produtos').child(id).delete()
    flash('Sucesso: Categoria removida permanentemente.', 'success')
    return redirect('/produtos')