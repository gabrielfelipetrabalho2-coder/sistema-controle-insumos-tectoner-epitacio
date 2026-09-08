from flask import Flask, render_template, request, redirect, flash
import firebase_admin
from firebase_admin import credentials, db

app = Flask(__name__)
app.secret_key = 'chave_secreta_super_segura'

# Inicializa o Firebase (verifica se já não foi inicializado antes)
cred = credentials.Certificate("firebase-key.json")
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred, {'databaseURL': 'https://scitectoner-default-rtdb.firebaseio.com/'})

@app.route('/')
def index():
    # Puxa os dados do banco
    locais_ref = db.reference('locais_prefeitura').get() or {}
    envios_ref = db.reference('envios').get() or {}
    
    lista_locais = [val['nome'] for key, val in locais_ref.items()]
    
    historico = []
    for key, val in envios_ref.items():
        folhas = int(val['folhas'])
        media = int(val['media_aplicada'])
        
        # Regra das mensagens de alerta por cores
        if folhas > media:
            val['cor'] = 'danger' # Vermelho
            val['status'] = 'Acima da Média'
        elif folhas == media:
            val['cor'] = 'warning' # Amarelo
            val['status'] = 'Na Média'
        else:
            val['cor'] = 'success' # Verde
            val['status'] = 'Abaixo da Média'
            
        historico.append(val)
        
    return render_template('index.html', locais=sorted(lista_locais), historico=historico)

@app.route('/registrar', methods=['POST'])
def registrar():
    local = request.form['local']
    folhas = int(request.form['folhas'])
    toners = int(request.form['toners'])
    
    # Média estipulada (1 caixa = 10 blocos de resmas)
    media_estipulada = 5000 
    
    # Salva o novo envio de insumos no banco de dados
    db.reference('envios').push({
        'local': local,
        'folhas': folhas,
        'toners': toners,
        'media_aplicada': media_estipulada
    })
    
    # Gera a mensagem que vai aparecer na tela
    if folhas > media_estipulada:
        flash(f'ALERTA: Foram enviadas {folhas} folhas para "{local}", ultrapassando o limite médio!', 'danger')
    elif folhas == media_estipulada:
        flash(f'Atenção: O envio para "{local}" atingiu exatamente o limite médio.', 'warning')
    else:
        flash(f'Sucesso: Envio para "{local}" registrado. Consumo dentro do padrão.', 'success')
        
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)