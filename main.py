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
API_KEY = 'afdf57ff-b687-497e-b6b9-b88c3e84f2b9-45caadf6-a5a2-458f-859d-82284a78a920'

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
        'Telefone': ', '.join([f"({telefone['area']}) {telefone['number']}" for telefone in dados_cnpj['phones']]),
        'Email': ', '.join([email['address'] for email in dados_cnpj['emails']]),
        'Atividade Principal': dados_cnpj['mainActivity']['text'],
        'Atividades Secundárias': ', '.join([activity['text'] for activity in dados_cnpj['sideActivities']]) if dados_cnpj['sideActivities'] else 'Nenhuma',
        'Simples Nacional Optante': dados_cnpj['company']['simples']['optant'] if 'simples' in dados_cnpj['company'] else 'Não disponível',
        'Simples Nacional Desde': dados_cnpj['company']['simples']['since'] if 'simples' in dados_cnpj['company'] else 'Não disponível',
        'SIMEI Optante': dados_cnpj['company']['simei']['optant'] if 'simei' in dados_cnpj['company'] else 'Não disponível',
        'SIMEI Desde': dados_cnpj['company']['simei']['since'] if 'simei' in dados_cnpj['company'] else 'Não disponível',
    }

    if 'registrations' in dados_cnpj and len(dados_cnpj['registrations']) > 0:
        inscricao_estadual = dados_cnpj['registrations'][0]
        dados['Inscrição Estadual Estado'] = inscricao_estadual['state']
        dados['Inscrição Estadual Número'] = inscricao_estadual['number']
        dados['Inscrição Estadual Status'] = inscricao_estadual['status']['text']
        dados['Inscrição Estadual Tipo'] = inscricao_estadual['type']['text']
        dados['Inscrição Estadual Data de Status'] = inscricao_estadual['statusDate']
    else:
        dados['Inscrição Estadual Estado'] = 'Não encontrada'
        dados['Inscrição Estadual Número'] = 'Não encontrada'
        dados['Inscrição Estadual Status'] = 'Não encontrada'
        dados['Inscrição Estadual Tipo'] = 'Não encontrada'
        dados['Inscrição Estadual Data de Status'] = 'Não encontrada'

    return dados

# Função para limpar o CNPJ
def limpar_cnpj(cnpj):
    return ''.join(e for e in str(cnpj) if e.isdigit())

# Função para verificar se o CNPJ já foi consultado (não usamos arquivos externos agora)
def verificar_cnpj_consultado(cnpj_limpo, resultados_anteriores):
    return cnpj_limpo in resultados_anteriores

# --- INTERFACE STREAMLIT ---
st.title("🔍 Consulta de CNPJ com Simples Nacional")

uploaded_file = st.file_uploader("📎 Carregue o arquivo XLSX com os CNPJs", type="xlsx")

if uploaded_file is not None:
    if st.button("🚀 Iniciar Consulta"):
        resultados = []
        cnpjs_consultados = set()
        progress_bar = st.progress(0)

        try:
            df_excel = pd.read_excel(uploaded_file)
            total_rows = len(df_excel)
        except Exception as e:
            st.error(f"❌ Erro ao ler o arquivo XLSX: {e}")
            st.stop()

        total_processed = 0

        for index, row in df_excel.iterrows():
            cnpj = str(row['CNPJ'])
            cnpj_limpo = limpar_cnpj(cnpj)

            if verificar_cnpj_consultado(cnpj_limpo, cnpjs_consultados):
                logging.info(f"CNPJ {cnpj_limpo} já consultado. Pulando...")
                continue

            logging.info(f"Iniciando consulta para o CNPJ: {cnpj_limpo}")
            dados_cnpj = consultar_cnpj(cnpj_limpo)
            if dados_cnpj:
                dados_empresa = extrair_dados_para_df(dados_cnpj)
                resultados.append(dados_empresa)
                cnpjs_consultados.add(cnpj_limpo)

            total_processed += 1
            progress_bar.progress(total_processed / total_rows)

            time.sleep(1)  # Espera de 1 segundo entre consultas

        if resultados:
            df_resultados = pd.DataFrame(resultados)
            st.success("✅ Consulta finalizada com sucesso!")

            st.dataframe(df_resultados)

            # Botão de download
            csv = df_resultados.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Baixar resultados em CSV",
                data=csv,
                file_name="resultados_consulta_cnpj.csv",
                mime='text/csv'
            )
        else:
            st.warning("Nenhum CNPJ foi consultado com sucesso.")
