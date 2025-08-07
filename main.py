import streamlit as st
import pandas as pd
import requests
import os
import time
from datetime import datetime
from io import BytesIO

# --- CONFIGURAÇÕES ---
API_KEY = 'afdf57ff-b687-497e-b6b9-b88c3e84f2b9-45caadf6-a5a2-458f-859d-82284a78a920'  # Substitua pela sua chave da API CNPJa
PASTA_SAIDA = 'consultas_cnpjs'
os.makedirs(PASTA_SAIDA, exist_ok=True)

# --- FUNÇÃO PARA CONSULTAR API ---
def consultar_cnpj(cnpj):
    url = f'https://api.cnpja.com/office/{cnpj}'
    headers = {'Authorization': f'Bearer {API_KEY}'}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.json()
        else:
            return {'erro': f'Erro {response.status_code}'}
    except requests.exceptions.RequestException as e:
        return {'erro': str(e)}

# --- STREAMLIT ---
st.set_page_config(page_title="Consulta CNPJ", layout="wide")
st.title("🔎 Consulta de CNPJs com CNPJa API")

arquivo = st.file_uploader("📤 Envie uma planilha com CNPJs", type=['xlsx', 'csv'])

if arquivo:
    if arquivo.name.endswith('.csv'):
        df = pd.read_csv(arquivo, dtype=str)
    else:
        df = pd.read_excel(arquivo, dtype=str)

    if 'CNPJ' not in df.columns:
        st.error("⚠️ A coluna 'CNPJ' não foi encontrada no arquivo.")
    else:
        df['CNPJ'] = df['CNPJ'].str.replace(r'\D', '', regex=True)
        df = df[df['CNPJ'].str.len() == 14].drop_duplicates(subset='CNPJ').reset_index(drop=True)

        st.success(f"✅ {len(df)} CNPJs prontos para consulta.")
        nome_arquivo_saida = os.path.join(PASTA_SAIDA, f'resultado_consulta_cnpj_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')

        if st.button("🚀 Iniciar Consulta"):
            resultados = []
            start_global = time.time()

            # Para evitar retrabalhos, verifique se já existe consulta anterior
            cnpjs_consultados = set()
            if os.path.exists(nome_arquivo_saida):
                df_existente = pd.read_csv(nome_arquivo_saida, dtype=str)
                cnpjs_consultados = set(df_existente['CNPJ'].dropna().unique())
                resultados.extend(df_existente.to_dict(orient='records'))

            total = len(df)
            barra = st.progress(0)
            status = st.empty()

            for i, row in df.iterrows():
                cnpj = row['CNPJ']

                if cnpj in cnpjs_consultados:
                    continue

                start_time = time.time()
                dados = consultar_cnpj(cnpj)
                tempo_consulta = time.time() - start_time

                registro = {'CNPJ': cnpj}

                if 'erro' in dados:
                    registro['Status'] = dados['erro']
                else:
                    registro['Razão Social'] = dados.get('razao_social')
                    registro['Nome Fantasia'] = dados.get('nome_fantasia')
                    registro['Situação Cadastral'] = dados.get('status')
                    registro['Data Abertura'] = dados.get('abertura')
                    registro['Porte'] = dados.get('porte')
                    registro['Natureza Jurídica'] = dados.get('natureza_juridica')
                    registro['CNAE Principal'] = dados.get('cnae_fiscal_descricao')
                    registro['Telefone'] = dados.get('ddd_telefone_1')
                    registro['Email'] = dados.get('email')
                    registro['UF'] = dados.get('uf')
                    registro['Município'] = dados.get('municipio')
                    registro['Bairro'] = dados.get('bairro')
                    registro['Logradouro'] = dados.get('logradouro')
                    registro['Número'] = dados.get('numero')
                    registro['CEP'] = dados.get('cep')
                    registro['Simples Nacional'] = dados.get('simples', {}).get('simples')
                    registro['MEI'] = dados.get('simples', {}).get('mei')
                    registro['IE'] = dados.get('inscricoes_estaduais', [{}])[0].get('inscricao_estadual')

                    registro['Status'] = 'OK'

                resultados.append(registro)
                cnpjs_consultados.add(cnpj)

                # Salvamento incremental
                pd.DataFrame(resultados).to_csv(nome_arquivo_saida, index=False)

                # Estimativa
                total_processados = len(cnpjs_consultados)
                tempo_total = time.time() - start_global
                tempo_medio = tempo_total / total_processados if total_processados else 0
                restante = total - total_processados
                tempo_restante = int(tempo_medio * restante)
                mins, secs = divmod(tempo_restante, 60)

                # Atualiza barra e status
                barra.progress(min(total_processados / total, 1.0))
                status.info(f"⏱️ {total_processados}/{total} processados | Estimativa restante: {mins}min {secs}s")

                # Pausa para evitar rate limit
                time.sleep(1)

            st.success("✅ Consulta finalizada!")
            st.dataframe(pd.DataFrame(resultados).tail(10))

            # Gera botão de download
            with open(nome_arquivo_saida, 'rb') as f:
                bytes_data = f.read()
            st.download_button("⬇️ Baixar resultado CSV", data=bytes_data, file_name=os.path.basename(nome_arquivo_saida), mime='text/csv')
