import streamlit as st
import pandas as pd
import requests
import logging
import os

# Configuração do logging (pode ser opcional em Streamlit)
logging.basicConfig(
    filename='consulta_cnpj.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Chave da API
API_KEY = '953c550f-fa61-461a-98d4-16671d4a4360-835686e9-0df7-4b35-a353-749dc2b19d7f'

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
        'Endereço': f"{dados_cnpj['address']['street']}, {dados_cnpj['address']['number']}, {dados_cnpj['address']['details']}, {dados_cnpj['address']['district']}, {dados_cnpj['address']['city']}/{dados_cnpj['address']['state']}, {dados_cnpj['address']['zip']}",
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
    # Inscrição Estadual
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

# Função para limpar os CNPJs
def limpar_cnpj(cnpj):
    return ''.join(e for e in str(cnpj) if e.isdigit())

# Função para verificar se o CNPJ já foi consultado
def verificar_cnpj_consultado(cnpj_limpo):
    arquivos_resultados = [
        r"G:\Meu Drive\BEES\consultas_cnpj_resultados2.csv",
        r"G:\Meu Drive\BEES\consultas_cnpj_resultados.csv",
    ]
    for arquivo in arquivos_resultados:
        if os.path.exists(arquivo):
            try:
                if arquivo.endswith("consultas_cnpj_resultados2.csv"):
                    df_existente = pd.read_csv(arquivo, dtype=str, sep=';', on_bad_lines='skip')
                elif arquivo.endswith("consultas_cnpj_resultados.csv"):
                    df_existente = pd.read_csv(arquivo, dtype=str, sep=',', on_bad_lines='skip')
                else:
                    continue  # Pular arquivos desconhecidos

                if cnpj_limpo in df_existente['CNPJ'].apply(limpar_cnpj).values:
                    return True
            except pd.errors.ParserError as e:
                logging.error(f"Erro ao ler arquivo {arquivo}: {e}")
    return False

# Interface Streamlit
st.title("Consulta de CNPJ com Simples Nacional")

uploaded_file = st.file_uploader("Carregue o arquivo XLSX com os CNPJs", type="xlsx")

if uploaded_file is not None:
    if st.button("Iniciar Consulta"):
        resultados = []  # Lista para armazenar os resultados

        progress_bar = st.progress(0)  # Barra de progresso

        try:
            df_excel = pd.read_excel(uploaded_file)
            total_rows = len(df_excel)  # Obtém o total de linhas do DataFrame
        except Exception as e:
            st.error(f"Erro ao ler o arquivo XLSX: {e}")
            st.stop()  # Para a execução se houver erro na leitura

        total_processed = 0
        try:
            # Itera sobre as linhas do DataFrame
            for index, row in df_excel.iterrows():
                cnpj = str(row['CNPJ'])  # Garante que CNPJ seja string
                cnpj_limpo = limpar_cnpj(cnpj)

                if verificar_cnpj_consultado(cnpj_limpo):
                    logging.info(f"CNPJ {cnpj_limpo} já consultado. Pulando...")
                    continue

                logging.info(f"Iniciando consulta para o CNPJ: {cnpj_limpo}")
                dados_cnpj = consultar_cnpj(cnpj_limpo)
                if dados_cnpj:
                    dados_empresa = extrair_dados_para_df(dados_cnpj)
                    resultados.append(dados_empresa)

                total_processed += 1
                progress_bar.progress(total_processed / total_rows)

        except Exception as e:
            st.error(f"Erro durante a consulta: {e}")
            st.stop()  # Para a execução se houver erro na consulta

        st.dataframe(pd.DataFrame(resultados))  # Exibir resultados como DataFrame

        # Salvar resultados em CSV na pasta especificada
        df_resultados = pd.DataFrame(resultados)
        pasta_destino = r"G:\Drives compartilhados\Cadastro BEES\CNPJ"
        nome_arquivo = "cnpjsconsultados.csv"
        caminho_completo = os.path.join(pasta_destino, nome_arquivo)

        try:
            df_resultados.to_csv(caminho_completo, index=False, encoding='utf-8')
            st.success(f"Consulta finalizada e arquivo CSV salvo em: {caminho_completo}")
        except Exception as e:
            st.error(f"Erro ao salvar o arquivo CSV: {e}")
