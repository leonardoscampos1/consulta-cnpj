import streamlit as st
import pandas as pd
import requests
import logging
import os
import time
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuração do logging
logging.basicConfig(
    filename='consulta_cnpj.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Chave da API
CHAVE_API = '1a18e6b7-c531-4335-bc58-281dbd02faaf-abd2b77a-73ca-45ae-ace2-e8d7bd13daf3'

# Função para consultar o CNPJ com múltiplas tentativas
def consultar_cnpj_com_tentativas(cnpj, max_tentativas=3, intervalo_segundos=15):
    url = f'https://api.cnpja.com/office/{cnpj}?simples=true&registrations=BR'
    headers = {'Authorization': CHAVE_API}
    for tentativa in range(max_tentativas):
        try:
            resposta = requests.get(url, headers=headers, timeout=30)  # Adicionado timeout
            if resposta.status_code == 200:
                logging.info(f"Consulta realizada com sucesso para o CNPJ: {cnpj}")
                return resposta.json()
            elif resposta.status_code == 429:
                logging.warning(f"Tentativa {tentativa + 1}: Limite de requisições excedido para o CNPJ {cnpj}. Aguardando...")
                time.sleep(intervalo_segundos * 2) # Espera mais tempo por causa do limite
            else:
                logging.warning(f"Tentativa {tentativa + 1}: Erro ao consultar CNPJ {cnpj}: {resposta.status_code}.")
            if tentativa < max_tentativas - 1:
                time.sleep(intervalo_segundos)
        except requests.exceptions.RequestException as e:
            logging.error(f"Tentativa {tentativa + 1}: Erro de requisição para o CNPJ {cnpj}: {e}.")
            if tentativa < max_tentativas - 1:
                time.sleep(intervalo_segundos)
    
    logging.error(f"Todas as {max_tentativas} tentativas para o CNPJ {cnpj} falharam.")
    return None

# Função para extrair os dados para o formato de dicionário
def extrair_dados_para_df(dados_cnpj):
    if not dados_cnpj:
        return {'CNPJ': 'Falha na Consulta', 'Nome': 'Não disponível', 'Status': 'Falha na Consulta'}
        
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
        'País': dados_cnpj['address']['country']['name'],
        'Telefone': ', '.join([f"({telefone['area']}) {telefone['number']}" for telefone in dados_cnpj.get('phones', [])]) if dados_cnpj.get('phones') else 'Não disponível',
        'Email': ', '.join([email['address'] for email in dados_cnpj.get('emails', [])]) if dados_cnpj.get('emails') else 'Não disponível',
        'Atividade Principal': dados_cnpj['mainActivity']['text'],
        'Atividades Secundárias': ', '.join([atividade['text'] for atividade in dados_cnpj.get('sideActivities', [])]) if dados_cnpj.get('sideActivities') else 'Nenhuma',
        'Simples Nacional Optante': dados_cnpj['company'].get('simples', {}).get('optant', 'Não disponível'),
        'Simples Nacional Desde': dados_cnpj['company'].get('simples', {}).get('since', 'Não disponível'),
        'SIMEI Optante': dados_cnpj['company'].get('simei', {}).get('optant', 'Não disponível'),
        'SIMEI Desde': dados_cnpj['company'].get('simei', {}).get('since', 'Não disponível'),
    }

    endereco = dados_cnpj.get('address', {})
    dados['Rua'] = endereco.get('street', 'Não disponível')
    dados['Número'] = endereco.get('number', 'Não disponível')
    dados['Complemento'] = endereco.get('details', 'Não disponível')
    dados['Bairro'] = endereco.get('district', 'Não disponível')
    dados['Cidade'] = endereco.get('city', 'Não disponível')
    dados['UF'] = endereco.get('state', 'Não disponível')
    dados['CEP'] = endereco.get('zip', 'Não disponível')
    
    if 'registrations' in dados_cnpj and dados_cnpj['registrations']:
        inscricao_estadual = dados_cnpj['registrations'][0]
        dados['Inscrição Estadual Estado'] = inscricao_estadual.get('state', 'Não encontrada')
        dados['Inscrição Estadual Número'] = inscricao_estadual.get('number', 'Não encontrada')
        dados['Inscrição Estadual Status'] = inscricao_estadual.get('status', {}).get('text', 'Não encontrada')
        dados['Inscrição Estadual Tipo'] = inscricao_estadual.get('type', {}).get('text', 'Não encontrada')
        dados['Inscrição Estadual Data de Status'] = inscricao_estadual.get('statusDate', 'Não encontrada')
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

# Função principal de consulta com multithreading
def consultar_todos_cnpjs(cnpjs, barra_de_progresso, status_texto, estimativa_tempo_placeholder):
    resultados = []
    cnpjs_com_falha = []
    total_linhas = len(cnpjs)
    total_processados = 0
    tempo_inicial = time.time()
    
    # Define o número de threads (ajuste conforme a capacidade da API e do seu sistema)
    num_threads = min(32, total_linhas)
    
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        # Envia as tarefas para o executor
        tarefas = {executor.submit(consultar_cnpj_com_tentativas, cnpj): cnpj for cnpj in cnpjs}
        
        for tarefa in as_completed(tarefas):
            cnpj = tarefas[tarefa]
            try:
                dados_cnpj = tarefa.result()
                if dados_cnpj:
                    dados_empresa = extrair_dados_para_df(dados_cnpj)
                    resultados.append(dados_empresa)
                else:
                    cnpjs_com_falha.append({'CNPJ': cnpj, 'Motivo da Falha': 'Não foi possível consultar após 3 tentativas.'})
            except Exception as e:
                logging.error(f"Erro ao processar a tarefa para o CNPJ {cnpj}: {e}")
                cnpjs_com_falha.append({'CNPJ': cnpj, 'Motivo da Falha': f'Erro inesperado: {e}'})
            
            total_processados += 1
            barra_de_progresso.progress(total_processados / total_linhas)
            status_texto.text(f"Consultando... {total_processados}/{total_linhas} CNPJs processados.")
            
            # Atualiza a estimativa de tempo
            try:
                tempo_decorrido = time.time() - tempo_inicial
                tempo_medio_por_item = tempo_decorrido / total_processados
                itens_restantes = total_linhas - total_processados
                tempo_restante_estimado = tempo_medio_por_item * itens_restantes
                
                m, s = divmod(tempo_restante_estimado, 60)
                h, m = divmod(m, 60)
                estimativa_tempo_placeholder.markdown(f"**Tempo restante estimado:** {int(h)}h {int(m)}min {int(s)}s")
            except:
                pass
                
    return resultados, cnpjs_com_falha

# Interface Streamlit
st.markdown("<h1 style='text-align: center; color: yellow;'>Consulta CNPJ</h3>", unsafe_allow_html=True)
st.markdown("<h3 style='text-align: center; color: blue;'>Criado por Leonardo Campos</h3>", unsafe_allow_html=True)
arquivo_carregado = st.file_uploader("Carregue o arquivo XLSX.", type="xlsx")
st.markdown("<h4 style='text-align: center; color: red;'>A coluna deve estar nomeada como 'CNPJ'</h3>", unsafe_allow_html=True)

if arquivo_carregado is not None:
    if st.button("Iniciar Consulta"):
        try:
            df_excel = pd.read_excel(arquivo_carregado)
            if 'CNPJ' not in df_excel.columns:
                st.error("A coluna 'CNPJ' não foi encontrada no arquivo. Por favor, verifique o nome da coluna.")
                st.stop()
            
            cnpjs_para_consultar = [limpar_cnpj(cnpj) for cnpj in df_excel['CNPJ'] if limpar_cnpj(cnpj)]
            if not cnpjs_para_consultar:
                st.warning("Nenhum CNPJ válido foi encontrado na coluna 'CNPJ'.")
                st.stop()

            st.info(f"Iniciando a consulta de {len(cnpjs_para_consultar)} CNPJs. Isso pode levar alguns minutos...")
            
            barra_de_progresso = st.progress(0)
            status_texto = st.empty()
            estimativa_tempo_placeholder = st.empty()
            
            resultados, cnpjs_com_falha = consultar_todos_cnpjs(cnpjs_para_consultar, barra_de_progresso, status_texto, estimativa_tempo_placeholder)

            status_texto.empty()
            estimativa_tempo_placeholder.empty()
            barra_de_progresso.progress(1.0)
            
            if resultados:
                df_resultados = pd.DataFrame(resultados)
                st.success("Consulta finalizada com sucesso!")
                st.dataframe(df_resultados)
    
                csv_buffer = BytesIO()
                df_resultados.to_csv(csv_buffer, index=False, encoding='utf-8-sig', sep=';')
                csv_buffer.seek(0)
                
                st.download_button(
                    label="Baixar arquivo CSV",
                    data=csv_buffer,
                    file_name="cnpjsconsultados.csv",
                    mime="text/csv",
                )
                
                st.write("---")
                st.markdown("Clique no botão acima para salvar o arquivo na pasta de sua escolha. O arquivo foi salvo com codificação **`UTF-8-SIG`** para aceitar caracteres especiais no Excel.")
            else:
                st.warning("Nenhum CNPJ foi consultado com sucesso.")

            if cnpjs_com_falha:
                st.write("---")
                st.error("Os seguintes CNPJs não puderam ser consultados:")
                df_falhas = pd.DataFrame(cnpjs_com_falha)
                st.dataframe(df_falhas)

        except Exception as e:
            st.error(f"Ocorreu um erro inesperado: {e}")
            logging.error(f"Erro na execução principal: {e}")
