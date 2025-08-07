import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime

st.set_page_config(page_title="Consulta de CNPJ em Massa", layout="wide")

st.title("🔍 Consulta de CNPJs em Massa - API CNPJ Já")

# Campo para colar a chave da API
api_key = 'afdf57ff-b687-497e-b6b9-b88c3e84f2b9-45caadf6-a5a2-458f-859d-82284a78a920'

# Upload do arquivo Excel
uploaded_file = st.file_uploader("📤 Envie um arquivo Excel com uma coluna chamada 'CNPJ':", type=["xlsx"])

if uploaded_file and api_key:
    df_excel = pd.read_excel(uploaded_file, dtype=str)
    
    if 'CNPJ' not in df_excel.columns:
        st.error("❌ A planilha deve conter uma coluna chamada 'CNPJ'.")
    else:
        if st.button("🚀 Iniciar Consulta"):
            total_rows = len(df_excel)
            resultados = []
            start_time = time.time()

            barra_progresso = st.progress(0, text="Iniciando...")
            texto_status = st.empty()

            for index, row in df_excel.iterrows():
                cnpj = str(row['CNPJ']).zfill(14)  # Corrige CNPJs com zeros à esquerda
                url = f"https://api.cnpja.com/office/{cnpj}"
                headers = {"Authorization": f"Bearer {api_key}"}

                try:
                    response = requests.get(url, headers=headers)
                    if response.status_code == 200:
                        data = response.json()
                        resultados.append({
                            "CNPJ": cnpj,
                            "Razão Social": data.get("razao_social"),
                            "Nome Fantasia": data.get("nome_fantasia"),
                            "Situação Cadastral": data.get("situacao_cadastral"),
                            "Porte": data.get("porte"),
                            "Natureza Jurídica": data.get("natureza_juridica", {}).get("descricao"),
                            "CNAE Principal": data.get("cnae_principal", {}).get("descricao"),
                            "Data Abertura": data.get("data_abertura"),
                            "UF": data.get("estado"),
                            "Município": data.get("municipio"),
                            "Telefone": data.get("telefone"),
                            "Email": data.get("email"),
                        })
                    else:
                        resultados.append({
                            "CNPJ": cnpj,
                            "Erro": f"Erro {response.status_code}"
                        })
                except Exception as e:
                    resultados.append({
                        "CNPJ": cnpj,
                        "Erro": str(e)
                    })

                # Progresso e estimativa
                progresso = int(((index + 1) / total_rows) * 100)
                barra_progresso.progress(progresso, text=f"⏳ Processando {index + 1} de {total_rows}...")

                # Estimativa de tempo restante
                tempo_passado = time.time() - start_time
                media = tempo_passado / (index + 1)
                restante = int(media * (total_rows - (index + 1)))
                min_rest, sec_rest = divmod(restante, 60)
                texto_status.caption(f"⏱️ Estimativa: {min_rest}min {sec_rest}s restantes")

            st.success("✅ Consulta finalizada!")

            df_resultados = pd.DataFrame(resultados)

            # Mostra resultados
            st.dataframe(df_resultados)

            # Nome do arquivo
            agora = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            nome_arquivo = f"resultado_consulta_cnpj_{agora}.csv"
            csv_bytes = df_resultados.to_csv(index=False).encode("utf-8")

            st.download_button(
                label="📥 Baixar resultados em CSV",
                data=csv_bytes,
                file_name=nome_arquivo,
                mime="text/csv"
            )
else:
    st.info("👆 Envie um arquivo Excel para começar.")

