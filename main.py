import streamlit as st
import pandas as pd
import requests
import logging
import os
import time
from io import BytesIO

# Configuração do logging
logging.basicConfig(
    filename='consulta_cnpj.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

API_KEY = 'afdf57ff-b687-497e-b6b9-b88c3e84f2b9-45caadf6-a5a2-458f-859d-82284a78a920'

def limpar_cnpj(cnpj):
    return ''.join(e for e in str(cnpj) if e.isdigit())

# Consulta com até 3 tentativas
def consultar_cnpj_com_retentativas(cnpj, max_tentativas=3):
    url = f'https://api.cnpja.com/office/{cnpj}?simples=true&registrations=BR'
    headers = {'Authorization': API_KEY}

    for tentativa in range(1, max_tentativas + 1):
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
            else:
                logging.warning(f"Tentativa {tentativa} falhou para o CNPJ {cnpj}: {response.status_code}")
                time.sleep(1)  # Espera curta entre tentativas
        except Exception as e:
            logging.error(f"Tentativa {tentativa} - Erro ao consultar CNPJ {cnpj}: {e}")
            time.sleep(1)

    return None  # Todas as tentativas falharam

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

# Streamlit
st.title("🔍 Consulta de CNPJ com Retentativas e Separação de Resultados")

uploaded_file = st.file_uploader("📂 Carregue o arquivo XLSX com os CNPJs", type="xlsx")

if uploaded_file is not None:
    if st.button("🚀 Iniciar Consulta"):
        try:
            df_excel = pd.read_excel(uploaded_file)
        except Exception as e:
            st.error(f"Erro ao ler o arquivo: {e}")
            st.stop()

        resultados = []
        falhas = []
        total = len(df_excel)
        progress = st.progress(0)

        for i, row in df_excel.iterrows():
            cnpj = limpar_cnpj(row.get("CNPJ", ""))
            if len(cnpj) != 14:
                falhas.append({'CNPJ': cnpj, 'Erro': 'Formato inválido'})
                progress.progress((i + 1) / total)
                continue

            dados = consultar_cnpj_com_retentativas(cnpj)
            if dados:
                resultados.append(extrair_dados_para_df(dados))
            else:
                falhas.append({'CNPJ': cnpj, 'Erro': 'Falha após 3 tentativas'})

            progress.progress((i + 1) / total)

        st.success("✅ Consulta finalizada!")

        # Exibir e permitir download dos que deram certo
        if resultados:
            df_resultados = pd.DataFrame(resultados)
            st.subheader("✅ CNPJs consultados com sucesso")
            st.dataframe(df_resultados)

            buffer = BytesIO()
            df_resultados.to_csv(buffer, index=False, encoding='utf-8')
            buffer.seek(0)
            st.download_button(
                label="📥 Baixar resultados CSV",
                data=buffer,
                file_name="resultado_consulta_cnpj.csv",
                mime="text/csv"
            )

        # Exibir e permitir download dos que falharam
        if falhas:
            df_falhas = pd.DataFrame(falhas)
            st.subheader("❌ CNPJs que falharam nas 3 tentativas")
            st.dataframe(df_falhas)

            buffer_erro = BytesIO()
            df_falhas.to_csv(buffer_erro, index=False, encoding='utf-8')
            buffer_erro.seek(0)
            st.download_button(
                label="📥 Baixar lista de CNPJs com erro",
                data=buffer_erro,
                file_name="cnpjs_falha.csv",
                mime="text/csv"
            )
