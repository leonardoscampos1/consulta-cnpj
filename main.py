import streamlit as st
import pandas as pd
import requests
import logging
import os
from io import BytesIO

# Configuração do logging
logging.basicConfig(
    filename='consulta_cnpj.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Chave da API
API_KEY = 'afdf57ff-b687-497e-b6b9-b88c3e84f2b9-45caadf6-a5a2-458f-859d-82284a78a920'

# Função para limpar CNPJ
def limpar_cnpj(cnpj):
    return ''.join(e for e in str(cnpj) if e.isdigit())

# Função para consultar o CNPJ com Simples Nacional
def consultar_cnpj(cnpj):
    url = f'https://api.cnpja.com/office/{cnpj}?simples=true&registrations=BR'
    headers = {'Authorization': API_KEY}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            logging.info(f"Consulta realizada com sucesso para o CNPJ: {cnpj}")
            return response.json()
        else:
            logging.error(f"Erro ao consultar CNPJ {cnpj}: {response.status_code}")
            return None
    except Exception as e:
        logging.error(f"Erro ao tentar consultar o CNPJ {cnpj}: {e}")
        return None

# Função para extrair os dados em formato de dicionário
def extrair_dados_para_df(dados_cnpj):
    dados = {
        'CNPJ': dados_cnpj['taxId'],
        'Nome': dados_cnpj['company']['name'],
        'Nome Fantasia': dados_cnpj.get('alias', 'Não disponível'),
        'Capital Social': dados_cnpj['company']['equity'],
        'Natureza Jurídica': dados_cnpj['company']['nature']['text'],
        'Tamanho': dados_cnpj['company']['size']['text'],
        'Data de Fundação': dados_cnpj['founded'],
        'Status': dados_cnpj['status']['text'],
        'Data de Status': dados_cnpj['statusDate'],
        'Razão de Status': dados_cnpj.get('reason', {}).get('text', 'Não disponível'),
        'Rua': dados_cnpj['address']['street'],
        'Número': dados_cnpj['address']['number'],
        'Complemento': dados_cnpj['address'].get('details', ''),
        'Bairro': dados_cnpj['address']['district'],
        'Cidade': dados_cnpj['address']['city'],
        'Estado': dados_cnpj['address']['state'],
        'CEP': dados_cnpj['address']['zip'],
        'País': dados_cnpj['address']['country']['name'],
        'Telefone': ', '.join([f"({t['area']}) {t['number']}" for t in dados_cnpj.get('phones', [])]),
        'Email': ', '.join([e['address'] for e in dados_cnpj.get('emails', [])]),
        'Atividade Principal': dados_cnpj['mainActivity']['text'],
        'Atividades Secundárias': ', '.join([a['text'] for a in dados_cnpj.get('sideActivities', [])]) or 'Nenhuma',
        'Simples Nacional Optante': dados_cnpj['company'].get('simples', {}).get('optant', 'Não disponível'),
        'Simples Nacional Desde': dados_cnpj['company'].get('simples', {}).get('since', 'Não disponível'),
        'SIMEI Optante': dados_cnpj['company'].get('simei', {}).get('optant', 'Não disponível'),
        'SIMEI Desde': dados_cnpj['company'].get('simei', {}).get('since', 'Não disponível'),
    }

    # Inscrição Estadual
    if 'registrations' in dados_cnpj and dados_cnpj['registrations']:
        reg = dados_cnpj['registrations'][0]
        dados.update({
            'Inscrição Estadual Estado': reg['state'],
            'Inscrição Estadual Número': reg['number'],
            'Inscrição Estadual Status': reg['status']['text'],
            'Inscrição Estadual Tipo': reg['type']['text'],
            'Inscrição Estadual Data de Status': reg['statusDate']
        })
    else:
        dados.update({
            'Inscrição Estadual Estado': 'Não encontrada',
            'Inscrição Estadual Número': 'Não encontrada',
            'Inscrição Estadual Status': 'Não encontrada',
            'Inscrição Estadual Tipo': 'Não encontrada',
            'Inscrição Estadual Data de Status': 'Não encontrada'
        })

    return dados

# Interface Streamlit
st.title("🔍 Consulta de CNPJ com Simples Nacional")

uploaded_file = st.file_uploader("📂 Carregue o arquivo XLSX com os CNPJs", type="xlsx")

if uploaded_file is not None:
    if st.button("🚀 Iniciar Consulta"):
        try:
            df_excel = pd.read_excel(uploaded_file)
        except Exception as e:
            st.error(f"Erro ao ler o arquivo: {e}")
            st.stop()

        resultados = []
        total = len(df_excel)
        progress = st.progress(0)

        for i, row in df_excel.iterrows():
            cnpj = limpar_cnpj(row.get("CNPJ", ""))
            if len(cnpj) != 14:
                logging.warning(f"CNPJ inválido: {cnpj}")
                continue

            dados = consultar_cnpj(cnpj)
            if dados:
                resultados.append(extrair_dados_para_df(dados))

            progress.progress((i + 1) / total)

        if resultados:
            df_resultados = pd.DataFrame(resultados)
            st.success("✅ Consulta finalizada com sucesso!")

            # Exibir os dados na interface
            st.dataframe(df_resultados)

            # Gerar CSV na memória para download
            buffer = BytesIO()
            df_resultados.to_csv(buffer, index=False, encoding='utf-8')
            buffer.seek(0)

            st.download_button(
                label="📥 Baixar resultados em CSV",
                data=buffer,
                file_name="resultado_consulta_cnpj.csv",
                mime="text/csv"
            )
        else:
            st.warning("⚠️ Nenhum dado foi retornado para os CNPJs consultados.")
