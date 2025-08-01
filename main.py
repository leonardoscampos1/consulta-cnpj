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

# Chave da API
CHAVE_API = '1a18e6b7-c531-4335-bc58-281dbd02faaf-abd2b77a-73ca-45ae-ace2-e8d7bd13daf3'

# Função para consultar o CNPJ com múltiplas tentativas (sem avisos na tela)
def consultar_cnpj_com_tentativas(cnpj, max_tentativas=3, intervalo_segundos=15):
    url = f'https://api.cnpja.com/office/{cnpj}?simples=true&registrations=BR'
    headers = {'Authorization': CHAVE_API}
    for tentativa in range(max_tentativas):
        try:
            resposta = requests.get(url, headers=headers)
            if resposta.status_code == 200:
                logging.info(f"Consulta realizada com sucesso para o CNPJ: {cnpj}")
                return resposta.json()
            else:
                logging.warning(f"Tentativa {tentativa + 1}: Erro ao consultar CNPJ {cnpj}: {resposta.status_code}.")
                if tentativa < max_tentativas - 1:
                    time.sleep(intervalo_segundos)
        except Exception as e:
            logging.error(f"Tentativa {tentativa + 1}: Erro ao tentar consultar o CNPJ {cnpj}: {e}.")
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
        'Telefone': ', '.join([f"({telefone['area']}) {telefone['number']}" for telefone in dados_cnpj['phones']]),
        'Email': ', '.join([email['address'] for email in dados_cnpj['emails']]),
        'Atividade Principal': dados_cnpj['mainActivity']['text'],
        'Atividades Secundárias': ', '.join([atividade['text'] for atividade in dados_cnpj['sideActivities']]) if dados_cnpj['sideActivities'] else 'Nenhuma',
        'Simples Nacional Optante': dados_cnpj['company']['simples']['optant'] if 'simples' in dados_cnpj['company'] else 'Não disponível',
        'Simples Nacional Desde': dados_cnpj['company']['simples']['since'] if 'simples' in dados_cnpj['company'] else 'Não disponível',
        'SIMEI Optante': dados_cnpj['company']['simei']['optant'] if 'simei' in dados_cnpj['company'] else 'Não disponível',
        'SIMEI Desde': dados_cnpj['company']['simei']['since'] if 'simei' in dados_cnpj['company'] else 'Não disponível',
    }

    endereco = dados_cnpj['address']
    dados['Rua'] = endereco['street']
    dados['Número'] = endereco['number']
    dados['Complemento'] = endereco.get('details', 'Não disponível')
    dados['Bairro'] = endereco['district']
    dados['Cidade'] = endereco['city']
    dados['UF'] = endereco['state']
    dados['CEP'] = endereco['zip']
    
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

# Função para verificar se o CNPJ já foi consultado (mantida para compatibilidade)
def verificar_cnpj_consultado(cnpj_limpo):
    return False

# Interface Streamlit
st.markdown("<h1 style='text-align: center; color: yellow;'>Consulta CNPJ</h3>", unsafe_allow_html=True)
st.markdown("<h3 style='text-align: center; color: blue;'>Criado por Leonardo Campos</h3>", unsafe_allow_html=True)
arquivo_carregado = st.file_uploader("Carregue o arquivo XLSX.", type="xlsx")
st.markdown("<h4 style='text-align: center; color: red;'>A coluna deve estar nomeada como 'CNPJ'</h3>", unsafe_allow_html=True)

if arquivo_carregado is not None:
    if st.button("Iniciar Consulta"):
        resultados = []
        cnpjs_com_falha = []
        barra_de_progresso = st.progress(0)
        status_texto = st.empty()

        try:
            df_excel = pd.read_excel(arquivo_carregado)
            total_linhas = len(df_excel)
        except Exception as e:
            st.error(f"Erro ao ler o arquivo XLSX: {e}")
            st.stop()

        total_processados = 0
        tempo_inicial = time.time()
        estimativa_tempo_placeholder = st.empty()

        try:
            for indice, linha in df_excel.iterrows():
                cnpj = str(linha['CNPJ'])
                cnpj_limpo = limpar_cnpj(cnpj)

                if verificar_cnpj_consultado(cnpj_limpo):
                    logging.info(f"CNPJ {cnpj_limpo} já consultado. Pulando...")
                    total_processados += 1
                    barra_de_progresso.progress(total_processados / total_linhas)
                    continue

                logging.info(f"Iniciando consulta para o CNPJ: {cnpj_limpo}")
                status_texto.text(f"Consultando CNPJ {cnpj_limpo} ({total_processados + 1}/{total_linhas})...")
                
                dados_cnpj = consultar_cnpj_com_tentativas(cnpj_limpo)

                if dados_cnpj:
                    dados_empresa = extrair_dados_para_df(dados_cnpj)
                    resultados.append(dados_empresa)
                else:
                    cnpjs_com_falha.append({'CNPJ': cnpj_limpo, 'Motivo da Falha': 'Não foi possível consultar após 3 tentativas.'})
                
                total_processados += 1
                barra_de_progresso.progress(total_processados / total_linhas)
                
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

        except Exception as e:
            st.error(f"Erro durante a consulta: {e}")
            st.stop()
        
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
            st.warning("Nenhum CNPJ foi consultado.")

        # --- Apresenta a lista de CNPJs com falha no final ---
        if cnpjs_com_falha:
            st.write("---")
            st.error("Os seguintes CNPJs não puderam ser consultados:")
            df_falhas = pd.DataFrame(cnpjs_com_falha)
            st.dataframe(df_falhas)
