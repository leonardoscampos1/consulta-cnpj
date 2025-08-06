import streamlit as st
import pandas as pd
import requests
import logging
import os
import time

# Configuração do logging
logging.basicConfig(
    filename='consulta_cnpj.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Chave da API
API_KEY = 'sua-chave-api-aqui'  # Substitua pela sua chave válida

# Função para consultar CNPJ com tratamento de erro 429
def consultar_cnpj(cnpj):
    url = f'https://api.cnpja.com/office/{cnpj}?simples=true&registrations=BR'
    headers = {'Authorization': API_KEY}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 429:
            logging.warning(f"Limite de requisições atingido para {cnpj}. Aguardando 60s...")
            time.sleep(60)
            return consultar_cnpj(cnpj)
        else:
            logging.error(f"Erro {response.status_code} ao consultar CNPJ {cnpj}: {response.text}")
            return None
    except Exception as e:
        logging.error(f"Erro ao tentar consultar o CNPJ {cnpj}: {e}")
        return None

# Função para extrair os dados para o formato de dicionário
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
            'Inscrição Estadual Data de Status': reg['statusDate'],
        })
    else:
        dados.update({
            'Inscrição Estadual Estado': 'Não encontrada',
            'Inscrição Estadual Número': 'Não encontrada',
            'Inscrição Estadual Status': 'Não encontrada',
            'Inscrição Estadual Tipo': 'Não encontrada',
            'Inscrição Estadual Data de Status': 'Não encontrada',
        })

    return dados

# Função para limpar CNPJ
def limpar_cnpj(cnpj):
    return ''.join(filter(str.isdigit, str(cnpj)))

# Verifica se já foi consultado
def verificar_cnpj_consultado(cnpj_limpo):
    arquivos = [
        r"G:\Meu Drive\BEES\consultas_cnpj_resultados2.csv",
        r"G:\Meu Drive\BEES\consultas_cnpj_resultados.csv",
    ]
    for arq in arquivos:
        if os.path.exists(arq):
            try:
                sep = ';' if '2.csv' in arq else ','
                df_existente = pd.read_csv(arq, dtype=str, sep=sep, on_bad_lines='skip')
                if cnpj_limpo in df_existente['CNPJ'].apply(limpar_cnpj).values:
                    return True
            except Exception as e:
                logging.error(f"Erro ao ler {arq}: {e}")
    return False

# ---- INTERFACE STREAMLIT ----

st.title("🔎 Consulta de CNPJ")

uploaded_file = st.file_uploader("📤 Carregue um arquivo XLSX com a coluna 'CNPJ'", type="xlsx")

if uploaded_file is not None:
    if st.button("🚀 Iniciar Consulta"):
        try:
            df_excel = pd.read_excel(uploaded_file)
            if 'CNPJ' not in df_excel.columns:
                st.error("❌ Coluna 'CNPJ' não encontrada no arquivo.")
                st.stop()
        except Exception as e:
            st.error(f"Erro ao ler o arquivo: {e}")
            st.stop()

        resultados = []
        total_rows = len(df_excel)
        total_processados = 0
        progress_bar = st.progress(0)

        for index, row in df_excel.iterrows():
            cnpj_raw = str(row['CNPJ'])
            cnpj_limpo = limpar_cnpj(cnpj_raw)

            if verificar_cnpj_consultado(cnpj_limpo):
                logging.info(f"CNPJ {cnpj_limpo} já consultado. Pulando.")
                continue

            with st.spinner(f"Consultando CNPJ {cnpj_limpo}..."):
                dados = consultar_cnpj(cnpj_limpo)
                if dados:
                    dados_empresa = extrair_dados_para_df(dados)
                    resultados.append(dados_empresa)
                else:
                    logging.warning(f"Dados não encontrados para CNPJ {cnpj_limpo}")

            total_processados += 1
            progress_bar.progress(total_processados / total_rows)
            time.sleep(0.7)  # evita sobrecarga da API

        st.info(f"✅ Consulta finalizada: {total_processados} de {total_rows} processados.")

        if resultados:
            df_resultados = pd.DataFrame(resultados)
            st.dataframe(df_resultados)

            csv_data = df_resultados.to_csv(index=False, encoding='utf-8')
            st.download_button(
                label="📥 Baixar CSV de Resultados",
                data=csv_data,
                file_name="cnpjs_consultados.csv",
                mime="text/csv"
            )
        else:
            st.warning("Nenhum dado novo foi consultado.")

