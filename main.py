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
                time.sleep(1)
        except Exception as e:
            logging.error(f"Tentativa {tentativa} - Erro ao consultar CNPJ {cnpj}: {e}")
            time.sleep(1)

    return None

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

# Estado da sessão
if 'resultados' not in st.session_state:
    st.session_state.resultados = []
if 'falhas' not in st.session_state:
    st.session_state.falhas = []

st.title("🔍 Consulta de CNPJ com Reprocessamento de Falhas")

uploaded_file = st.file_uploader("📂 Carregue o arquivo XLSX com os CNPJs", type="xlsx")

if uploaded_file is not None:
    if st.button("🚀 Iniciar Consulta"):
        try:
            df_excel = pd.read_excel(uploaded_file)
        except Exception as e:
            st.error(f"Erro ao ler o arquivo: {e}")
            st.stop()

        st.session_state.resultados = []
        st.session_state.falhas = []

        total = len(df_excel)
        progress = st.progress(0)

        for i, row in df_excel.iterrows():
            cnpj = limpar_cnpj(row.get("CNPJ", ""))
            if len(cnpj) != 14:
                st.session_state.falhas.append({'CNPJ': cnpj, 'Erro': 'Formato inválido'})
                progress.progress((i + 1) / total)
                continue

            dados = consultar_cnpj_com_retentativas(cnpj)
            if dados:
                st.session_state.resultados.append(extrair_dados_para_df(dados))
            else:
                st.session_state.falhas.append({'CNPJ': cnpj, 'Erro': 'Falha após 3 tentativas'})

            progress.progress((i + 1) / total)

        st.success("✅ Consulta inicial finalizada!")

# Exibir resultados e botões
if st.session_state.resultados:
    df_ok = pd.DataFrame(st.session_state.resultados)
    st.subheader("✅ CNPJs consultados com sucesso")
    st.dataframe(df_ok)

    buffer = BytesIO()
    df_ok.to_csv(buffer, index=False, encoding='utf-8')
    buffer.seek(0)
    st.download_button("📥 Baixar resultados CSV", data=buffer, file_name="resultado_consulta_cnpj.csv", mime="text/csv")

if st.session_state.falhas:
    df_falha = pd.DataFrame(st.session_state.falhas)
    st.subheader("❌ CNPJs com erro")
    st.dataframe(df_falha)

    buffer_erro = BytesIO()
    df_falha.to_csv(buffer_erro, index=False, encoding='utf-8')
    buffer_erro.seek(0)
    st.download_button("📥 Baixar lista de CNPJs com erro", data=buffer_erro, file_name="cnpjs_falha.csv", mime="text/csv")

    if st.button("🔁 Reprocessar CNPJs com erro"):
        novos_resultados = []
        erros_atuais = []

        progress = st.progress(0)
        total = len(st.session_state.falhas)

        for i, item in enumerate(st.session_state.falhas):
            cnpj = limpar_cnpj(item['CNPJ'])
            if len(cnpj) != 14:
                erros_atuais.append({'CNPJ': cnpj, 'Erro': 'Formato inválido'})
                progress.progress((i + 1) / total)
                continue

            dados = consultar_cnpj_com_retentativas(cnpj)
            if dados:
                novos_resultados.append(extrair_dados_para_df(dados))
            else:
                erros_atuais.append({'CNPJ': cnpj, 'Erro': 'Falha após reprocessamento'})

            progress.progress((i + 1) / total)

        st.session_state.resultados.extend(novos_resultados)
        st.session_state.falhas = erros_atuais
