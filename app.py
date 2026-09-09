from flask import Flask, render_template, request, redirect, flash
import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'chave_secreta_super_segura'

cred = credentials.Certificate("firebase-key.json")
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred, {'databaseURL': 'https://scitectoner-default-rtdb.firebaseio.com/'})

@app.route('/')
def index():
    locais_ref = db.reference('locais_prefeitura').get() or {}
    envios_ref = db.reference('envios').get() or {}
    
    # Agora passamos o ID, Nome e se a exclusão é permitida (locais manuais)
    lista_locais = []
    for key, val in locais_ref.items():
        lista_locais.append({
            'id': key,
            'nome': val.get('nome', ''),
            'removivel': val.get('removivel', False) # Os da planilha serão False
        })
    # Ordena alfabeticamente
    lista_locais = sorted(lista_locais, key=lambda x: x['nome'])
    
    historico_mes = []
    dados_grafico = {}
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
            else:
                dados_grafico[local_nome] = folhas
                
    historico_mes.reverse()
    
    return render_template('index.html', locais=lista_locais, historico=historico_mes, dados_grafico=dados_grafico, mes_atual=mes_atual)

@app.route('/registrar', methods=['POST'])
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
        flash('Erro: Você deve registrar o envio de pelo menos 1 Folha OU 1 Toner.', 'danger')
        return redirect('/')
    
    if data_input:
        data_obj = datetime.strptime(data_input, '%Y-%m-%d')
        dia_escolhido = data_obj.strftime('%d/%m')
        mes_ref_registro = data_obj.strftime('%m/%Y')
    else:
        dia_escolhido = datetime.now().strftime('%d/%m')
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
        if media_final <= 0:
            flash('Erro: A média informada deve ser maior que zero.', 'danger')
            return redirect('/')
    else:
        if registro_existente_dados:
            media_final = int(registro_existente_dados.get('media_aplicada', 5000))
        else:
            media_final = 5000
            
    if registro_existente_id:
        folhas_antigas = int(registro_existente_dados.get('folhas', 0))
        toners_antigos = int(registro_existente_dados.get('toners', 0))
        datas_antigas = str(registro_existente_dados.get('data', ''))
        
        nova_data = f"{datas_antigas}, {dia_escolhido}" if dia_escolhido not in datas_antigas else datas_antigas
        
        envios_ref.child(registro_existente_id).update({
            'folhas': folhas_antigas + folhas,
            'toners': toners_antigos + toners,
            'media_aplicada': media_final,
            'data': nova_data
        })
        flash(f'Sucesso: Entrega do dia {dia_escolhido} somada para "{local}".', 'success')
    else:
        envios_ref.push({
            'local': local,
            'folhas': folhas,
            'toners': toners,
            'media_aplicada': media_final,
            'data': dia_escolhido,
            'mes_ref': mes_ref_registro
        })
        flash(f'Sucesso: Primeira entrega do mês iniciada para "{local}".', 'success')
        
    return redirect('/')

@app.route('/deletar/<id>')
def deletar(id):
    db.reference('envios').child(id).delete()
    flash('Registro mensal deletado com sucesso!', 'success')
    return redirect('/')

@app.route('/editar/<id>', methods=['GET', 'POST'])
def editar(id):
    if request.method == 'POST':
        media = int(request.form.get('media', 5000))
        folhas = int(request.form.get('folhas', 0))
        toners = int(request.form.get('toners', 0))
        datas_editadas = request.form.get('datas_historico', '')
        
        if folhas < 0 or toners < 0 or media <= 0:
            flash('Erro: Valores inválidos!', 'danger')
            return redirect(f'/editar/{id}')
            
        db.reference('envios').child(id).update({
            'media_aplicada': media,
            'folhas': folhas,
            'toners': toners,
            'data': datas_editadas
        })
        flash('Totais do mês corrigidos com sucesso!', 'success')
        return redirect('/')
        
    else:
        registro = db.reference('envios').child(id).get()
        return render_template('editar.html', registro=registro, id=id)

@app.route('/novo_local', methods=['GET', 'POST'])
def novo_local():
    if request.method == 'POST':
        nome_local = request.form.get('nome_local', '').strip()
        if not nome_local:
            flash('Erro: O nome do local não pode ficar vazio.', 'danger')
            return redirect('/novo_local')
            
        db.reference('locais_prefeitura').push({
            'nome': nome_local,
            'media_folhas': 5000,
            'removivel': True # A ETIQUETA INVISÍVEL!
        })
        flash(f'Sucesso: O novo local "{nome_local}" foi cadastrado no sistema!', 'success')
        return redirect('/')
        
    return render_template('novo_local.html')

# NOVA ROTA: DELETAR LOCAL MANUAL
@app.route('/deletar_local/<id>')
def deletar_local(id):
    db.reference('locais_prefeitura').child(id).delete()
    flash('Local customizado excluído permanentemente!', 'success')
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)