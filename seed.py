import pandas as pd
import firebase_admin
from firebase_admin import credentials, db

# Inicializa o Firebase com a sua chave e a URL do seu banco
cred = credentials.Certificate("firebase-key.json")
firebase_admin.initialize_app(cred, {'databaseURL': 'https://scitectoner-default-rtdb.firebaseio.com/'})

print("Lendo a planilha do Excel...")
xls = pd.ExcelFile('Impressoras da Prefeitura.xlsx')
locais_unicos = set()

# Varre todas as abas da planilha procurando a coluna 'Local'
for aba in xls.sheet_names:
    df = pd.read_excel('Impressoras da Prefeitura.xlsx', sheet_name=aba, skiprows=1)
    if 'Local' in df.columns:
        locais_unicos.update(df['Local'].dropna().tolist())

# Salva os locais de Presidente Epitácio no Firebase
ref = db.reference('locais_prefeitura')
ref.set({}) # Limpa dados antigos para não duplicar
for local in locais_unicos:
    # 5000 folhas = 10 blocos de resmas com 500 folhas (média estipulada)
    ref.push({'nome': str(local), 'media_folhas': 5000}) 

print(f"{len(locais_unicos)} locais importados com sucesso para o Firebase!")