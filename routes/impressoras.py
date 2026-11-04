from flask import Blueprint, render_template, request, redirect, flash
from firebase_admin import db
from datetime import datetime

impressoras_bp = Blueprint('impressoras', __name__, url_prefix='/impressoras')

@impressoras_bp.route('/')
def index():
    impressoras_ref = db.reference('impressoras').get() or {}
    lista_impressoras = []
    
    for key, val in impressoras_ref.items():
        val['id'] = key
        lista_impressoras.append(val)
        
    # Organiza por data mais recente por padrão (se houver data)
    lista_impressoras.sort(key=lambda x: x.get('data_registro', ''), reverse=True)
    
    return render_template('impressoras.html', impressoras=lista_impressoras, data_hoje=datetime.now().strftime('%Y-%m-%d'))

@impressoras_bp.route('/nova', methods=['POST'])
def nova_impressora():
    dados = {
        'data_registro': request.form.get('data_registro'),
        'modelo': request.form.get('modelo'),
        'setor': request.form.get('setor'),
        'numero_serie': request.form.get('numero_serie', ''),
        'serial_antigo': request.form.get('serial_antigo', ''),
        'serial_novo': request.form.get('serial_novo', ''),
        'contador_paginas': request.form.get('contador_paginas', '0'),
        'status': request.form.get('status'),
        'prioridade': request.form.get('prioridade'),
        'motivo': request.form.get('motivo', '')
    }
    
    db.reference('impressoras').push(dados)
    flash('Impressora cadastrada com sucesso!', 'success')
    return redirect('/impressoras')

@impressoras_bp.route('/deletar/<id>')
def deletar(id):
    db.reference('impressoras').child(id).delete()
    flash('Registro da impressora excluído!', 'success')
    return redirect('/impressoras')

@impressoras_bp.route('/editar/<id>', methods=['GET', 'POST'])
def editar(id):
    registro = db.reference('impressoras').child(id).get()
    
    if not registro:
        flash('Impressora não encontrada.', 'danger')
        return redirect('/impressoras')
        
    if request.method == 'POST':
        dados_atualizados = {
            'data_registro': request.form.get('data_registro'),
            'modelo': request.form.get('modelo'),
            'setor': request.form.get('setor'),
            'numero_serie': request.form.get('numero_serie', ''),
            'serial_antigo': request.form.get('serial_antigo', ''),
            'serial_novo': request.form.get('serial_novo', ''),
            'contador_paginas': request.form.get('contador_paginas', '0'),
            'status': request.form.get('status'),
            'prioridade': request.form.get('prioridade'),
            'motivo': request.form.get('motivo', '')
        }
        db.reference('impressoras').child(id).update(dados_atualizados)
        flash('Status da impressora atualizado com sucesso!', 'success')
        return redirect('/impressoras')
        
    return render_template('impressoras_editar.html', registro=registro, id=id)