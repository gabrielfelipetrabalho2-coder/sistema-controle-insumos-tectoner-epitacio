from flask import Flask, render_template, request, redirect, flash
import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'chave_secreta_super_segura'

# Inicializa o Firebase
cred = credentials.Certificate("firebase-key.json")
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred, {'databaseURL': 'https://scitectoner-default-rtdb.firebaseio.com/'})

@app.route('/')
def index():
    locais_ref = db.reference('locais_prefeitura').get() or {}
    envios_ref = db.reference('envios').get() or {}
    
    lista_locais = [val['nome'] for key, val in locais_ref.items()]
    
    historico = []
    dados_grafico = {} 
    
    for key, val in envios_ref.items():
        val['id'] = key 
        folhas = int(val['folhas'])
        # Agora a média é lida do banco, com base no que você digitou no cadastro
        media = int(val.get('media_aplicada', 5000)) 
        
        if 'data' not in val:
            val['data'] = 'Data não registrada'
            
        if folhas > media:
            val['cor'] = 'danger'
            val['status'] = 'Acima da Média'
        elif folhas == media:
            val['cor'] = 'warning'
            val['status'] = 'Na Média'
        else:
            val['cor'] = 'success'
            val['status'] = 'Abaixo da Média'
            
        historico.append(val)
        
        local_nome = val['local']
        if local_nome in dados_grafico:
            dados_grafico[local_nome] += folhas
        else:
            dados_grafico[local_nome] = folhas
            
    historico.reverse()
    return render_template('index.html', locais=sorted(lista_locais), historico=historico, dados_grafico=dados_grafico)

@app.route('/registrar', methods=['POST'])
def registrar():
    local = request.form['local']
    media = int(request.form['media'])
    folhas = int(request.form['folhas'])
    toners = int(request.form['toners'])
    
    # Validação Back-end: bloqueia 0 e números negativos
    if folhas <= 0 or toners <= 0 or media <= 0:
        flash('Erro: Não é possível enviar 0 caixas. Os valores devem ser maiores que zero!', 'danger')
        return redirect('/')
    
    data_atual = datetime.now().strftime('%d/%m/%Y %H:%M')
    
    db.reference('envios').push({
        'local': local,
        'folhas': folhas,
        'toners': toners,
        'media_aplicada': media,
        'data': data_atual
    })
    
    flash(f'Sucesso: Envio para "{local}" registrado na data {data_atual}.', 'success')
    return redirect('/')

@app.route('/deletar/<id>')
def deletar(id):
    db.reference('envios').child(id).delete()
    flash('Registro deletado com sucesso!', 'success')
    return redirect('/')

@app.route('/editar/<id>', methods=['GET', 'POST'])
def editar(id):
    if request.method == 'POST':
        media = int(request.form['media'])
        folhas = int(request.form['folhas'])
        toners = int(request.form['toners'])
        
        # Bloqueia 0 e negativos também na edição
        if folhas <= 0 or toners <= 0 or media <= 0:
            flash('Erro: Valores iguais ou menores que zero não são permitidos!', 'danger')
            return redirect(f'/editar/{id}')
            
        db.reference('envios').child(id).update({
            'media_aplicada': media,
            'folhas': folhas,
            'toners': toners
        })
        flash('Registro atualizado com sucesso!', 'success')
        return redirect('/')
        
    else:
        registro = db.reference('envios').child(id).get()
        return render_template('editar.html', registro=registro, id=id)

if __name__ == '__main__':
    app.run(debug=True)