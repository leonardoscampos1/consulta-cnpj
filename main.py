import streamlit as st
import pandas as pd
import requests
import os
import time
from datetime import datetime
from pathlib import Path

# --- CONFIGURAÇÕES ---
API_KEY = "SUA_CHAVE_AQUI"  # Substitua por sua chave da API CNPJa
API_URL = "https://api.cnpja.com/office/"
PASTA_SAIDA = "resultados_consulta"
ARQUIVO_SAIDA = "consulta_cnpjs.csv"
TEMPO_ESPERA = 1.2  # segundos entre chamadas (ajustável)

# --- CRIA PASTA SE NÃO EXISTIR ---
Path(PASTA_SAIDA).mkdir(parents=True, exist_ok=True)
CAMINHO_CSV = os.path.join(PASTA_SAIDA, ARQUIVO_SAIDA)

# --- FUNÇÃO: CONSULTA CNPJ ---
def consultar_cnpj(cnpj):
    try:
        url = f"{API_URL}{cnpj}"
        headers = {"Authorization": f"Bearer {API_KEY}"}
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            return {
                "CNPJ": data.get("establishment", {}).get("cnpj"),
                "Razão Social": data.get("company", {}).get("name"),
                "Nome Fantasia": data.get("establishment", {}).get("fantasy_name"),
                "Situação Cadastral": data.get("establishment", {}).get("status"),
                "Data Abertura": data.get("establishment", {}).get("opening_date"),
                "Porte": data.get("company", {}).get("size"),
                "CNAE Principal": data.get("establishment", {}).get("main_activity", {}).get("title"),
                "Inscrição Estadual": data.get("establishment", {}).get("state_registration"),
                "Simples Nacional": data.get("simples", {}).get("simples_nacional", {}).get("optante"),
                "MEI": data.get("simples", {}).get("mei", {}).get("optante"),
                "UF": data.get("establishment", {}).get("state"),
                "Município": data.get("establishment", {}).get("city"),
                "Bairro": data.get("establishment", {}).get("neighborhood"),
                "Logradouro": data.get("establishment", {}).get("street"),
                "Número": data.get("establishment", {}).get("number"),
                "Complemento": data.get("establishment", {}).get("complement"),
                "CEP": data.get("establishment", {}).get("zipcode"),
            }
        else:
            return {"CNPJ": cnpj, "Erro": f"Erro {response.status_code}: {response.text}"}
    except Exception as e:
        return {"CNPJ": cnpj, "Erro": str(e)}

# --- CARREGA DADOS EXISTENTES ---
def carregar_dados_existentes():
    if os.path.exists(CAMINHO_CSV):
        return pd.read_csv(CAMINHO_CSV, dtype=str)
    return pd.DataFrame()

# --- SALVA NOVO RESULTADO INCREMENTAL ---
def salvar_resultado(resultado):
    df_novo = pd.DataFrame([resultado])
    if os.path.exists(CAMINHO_CSV):
        df_novo.to_csv(CAMINHO_CSV, mode='a', header=False, index=False)
    else:
        df_novo.to_csv(CAMINHO_CSV, index=False)

# --- INTERFACE STREAMLIT ---
st.set_page_config("Consulta CNPJ", layout="centered")
st.title("🔍 Consulta de CNPJs com API CNPJa")
st.caption("Evita duplicações, salva automaticamente e mostra tempo estimado.")

arquivo = st.file_uploader("📤 Envie um arquivo CSV com CNPJs (coluna única ou nomeada)", type=["csv"])
btn_iniciar = st.button("🚀 Iniciar Consulta")

if btn_iniciar and arquivo:
    df_input = pd.read_csv(arquivo, dtype=str)
    colunas_validas = df_input.columns.tolist()

    # Determina coluna de CNPJs
    if "CNPJ" in colunas_validas:
        cnpjs = df_input["CNPJ"].dropna().astype(str).str.replace(r'\D', '', regex=True)
    else:
        cnpjs = df_input.iloc[:, 0].dropna().astype(str).str.replace(r'\D', '', regex=True)

    cnpjs = cnpjs[cnpjs.str.len() == 14].unique().tolist()
    total = len(cnpjs)
    st.success(f"✅ {total} CNPJs carregados para consulta.")

    # Carrega dados anteriores
    dados_existentes = carregar_dados_existentes()
    cnpjs_já_consultados = set(dados_existentes["CNPJ"]) if not dados_existentes.empty else set()

    progresso = st.progress(0)
    status_text = st.empty()
    inicio = time.time()

    for idx, cnpj in enumerate(cnpjs, start=1):
        if cnpj in cnpjs_já_consultados:
            continue

        resultado = consultar_cnpj(cnpj)
        salvar_resultado(resultado)

        # Tempo estimado
        tempo_passado = time.time() - inicio
        media_por_item = tempo_passado / idx
        restante = (total - idx) * media_por_item
        estimativa = time.strftime("%Mmin %Ss", time.gmtime(restante))

        progresso.progress(idx / total)
        status_text.markdown(f"📦 Processado {idx} de {total} | ⏱️ Estimativa restante: {estimativa}")
        time.sleep(TEMPO_ESPERA)

    st.success("✅ Consulta finalizada!")
    st.download_button("📥 Baixar resultado CSV", data=open(CAMINHO_CSV, "rb"), file_name=ARQUIVO_SAIDA, mime="text/csv")
