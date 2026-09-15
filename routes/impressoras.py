from flask import Blueprint, render_template, request, redirect, flash
from firebase_admin import db

impressoras_bp = Blueprint('impressoras', __name__)


@impressoras_bp.route('/impressoras')
def index():
    # Busca as impressoras no banco de dados
    impressoras_ref = db.reference('impressoras').get() or {}

    lista_impressoras = []
    for key, val in impressoras_ref.items():
        val['id'] = key
        lista_impressoras.append(val)

    # Ordena pelo setor para facilitar a visualização
    lista_impressoras = sorted(
        lista_impressoras, key=lambda x: x.get('setor', ''))

    return render_template('impressoras.html', impressoras=lista_impressoras)


@impressoras_bp.route('/impressoras/nova', methods=['POST'])
def nova_impressora():
    dados = {
        'modelo': request.form.get('modelo').strip(),
        'numero_serie': request.form.get('numero_serie').strip(),
        'setor': request.form.get('setor').strip(),
        'contador_paginas': request.form.get('contador_paginas').strip(),
        'status': request.form.get('status')
    }

    db.reference('impressoras').push(dados)
    flash('Sucesso: Impressora registrada no sistema!', 'success')
    return redirect('/impressoras')


@impressoras_bp.route('/impressoras/deletar/<id>')
def deletar_impressora(id):
    db.reference('impressoras').child(id).delete()
    flash('Sucesso: Registro da impressora removido.', 'success')
    return redirect('/impressoras')
