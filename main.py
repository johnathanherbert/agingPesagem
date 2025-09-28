import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, date
import os

# --- Configurações Iniciais da Página ---
st.set_page_config(
    page_title="Dashboard de Aging de Matérias-Primas",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Inicialização do Session State para Persistência ---
# Inicializa o DataFrame no estado da sessão (st.session_state)
if 'df_data' not in st.session_state:
    st.session_state.df_data = pd.DataFrame()
if 'hoje_data' not in st.session_state:
    st.session_state.hoje_data = date.today()
if 'uploaded_file_name' not in st.session_state:
    st.session_state.uploaded_file_name = None

# --- Função de Carregamento e Processamento de Dados ---
@st.cache_data
def load_and_process_data(data_source):
    """Carrega, limpa e processa os dados da planilha, aceitando path ou arquivo carregado (CSV ou XLSX)."""
    
    # Determina se o arquivo é Excel ou CSV baseado na extensão ou tipo de arquivo Streamlit
    is_excel = False
    if isinstance(data_source, str) and (data_source.endswith('.xlsx') or data_source.endswith('.xls')):
        is_excel = True
    elif hasattr(data_source, 'name') and (data_source.name.endswith('.xlsx') or data_source.name.endswith('.xls')):
        is_excel = True
        
    try:
        # A planilha tem 3 linhas de cabeçalho antes do cabeçalho real (índice 3), então usamos header=3 (index 4)
        header_row = 3
        
        # Definir tipos de colunas (dtype) para garantir que 'Material' seja lido como string
        dtype_spec = {0: str} # Coluna 0 (Material) forçada para string

        if is_excel:
            # Usar pd.read_excel para arquivos XLSX
            df = pd.read_excel(data_source, header=header_row, engine='openpyxl', dtype=dtype_spec)
        else:
            # Usar pd.read_csv para arquivos CSV
            df = pd.read_csv(data_source, sep=',', encoding='utf-8', header=header_row, engine='python', dtype=dtype_spec)

        # Nomes esperados após pular as 3 primeiras linhas:
        df.columns = [
            'Material', 'Descricao_Material', 'Lote', 'Estoque_Disponivel',
            'UMB', 'Tipo_Estoque', 'Data_Entrada', 'Ultimo_Movimento'
        ]
        
        # --- TRATAMENTO DE ESTOQUE DISPONÍVEL ---
        # 1. Converter valores para string e substituir ',' por '.' para garantir formato float
        df['Estoque_Disponivel'] = df['Estoque_Disponivel'].astype(str).str.replace(',', '.', regex=False)
        # 2. Converter para numérico (coerce lida com quaisquer falhas)
        df['Estoque_Disponivel'] = pd.to_numeric(df['Estoque_Disponivel'], errors='coerce')
        # Remover linhas com estoque NaN, se houver
        df.dropna(subset=['Estoque_Disponivel'], inplace=True)
        # -------------------------------------------------

        # Converter a coluna 'Último movimento' para datetime
        # Tentamos formatos comuns, incluindo o 'AAAA-MM-DD' que aparece no snippet.
        df['Ultimo_Movimento'] = pd.to_datetime(df['Ultimo_Movimento'], errors='coerce', dayfirst=False)

        # Remover linhas onde a data é inválida
        df.dropna(subset=['Ultimo_Movimento'], inplace=True)

        # 1. Calcular o (Aging) em dias
        hoje = date.today()
        # Calcula a diferença de dias entre a data de hoje e a data do último movimento
        df['Dias_Em_Estoque'] = (pd.to_datetime(hoje) - df['Ultimo_Movimento']).dt.days

        # 2. Criar a Coluna de Categoria (Aging Category)
        # Normal: < 10 dias
        # Alerta: >= 10 dias e < 20 dias
        # Crítico: >= 20 dias
        def categorizar_aging(dias):
            if dias < 10:
                return 'Normal'
            elif 10 <= dias < 20:
                return 'Alerta'
            else:
                return 'Crítico'

        df['Categoria_Aging'] = df['Dias_Em_Estoque'].apply(categorizar_aging)

        # Criar coluna de cores para os gráficos
        color_map = {'Normal': 'green', 'Alerta': 'orange', 'Crítico': 'red'}
        df['Cor_Categoria'] = df['Categoria_Aging'].map(color_map)

        return df, hoje

    except Exception as e:
        st.error(f"Ocorreu um erro no processamento dos dados. Verifique se o arquivo é um CSV ou Excel (.xlsx) e se o cabeçalho (4ª linha) está no formato esperado.")
        st.error(f"Detalhes do erro: {e}")
        return pd.DataFrame(), date.today()

# --- Função para Limpar os Dados ---
def clear_data():
    """Limpa o session_state para permitir novo upload."""
    st.session_state.df_data = pd.DataFrame()
    st.session_state.hoje_data = date.today()
    st.session_state.uploaded_file_name = None
    st.rerun()

# --- Componente principal do App ---

st.title("💊 Aging Pesagem") # Título atualizado
# Usa a data armazenada no session_state
st.markdown(f"**Data de Referência:** {st.session_state.hoje_data.strftime('%d/%m/%Y')}")
st.divider()

# Nome do arquivo esperado (para carregamento automático local, se a sessão estiver vazia)
EXPECTED_FILE_NAME = "EXPORT_20250211_144147.xlsx" 
df = st.session_state.df_data
hoje = st.session_state.hoje_data
loaded_from_file = False

# --- Lógica de Carregamento (Prioriza Session State) ---
if df.empty:
    # 1. Tentar carregar o arquivo padrão se estiver no diretório (apenas na primeira execução)
    if os.path.exists(EXPECTED_FILE_NAME):
        df, hoje = load_and_process_data(EXPECTED_FILE_NAME)
        if not df.empty:
            st.session_state.df_data = df
            st.session_state.hoje_data = hoje
            st.session_state.uploaded_file_name = EXPECTED_FILE_NAME
            
            try:
                timestamp = os.path.getmtime(EXPECTED_FILE_NAME)
                last_modified_date = datetime.fromtimestamp(timestamp).strftime('%d/%m/%Y %H:%M:%S')
                st.info(f"Dados carregados automaticamente do arquivo: **{EXPECTED_FILE_NAME}** (Última Modificação: {last_modified_date})")
            except OSError:
                st.info(f"Dados carregados automaticamente do arquivo: **{EXPECTED_FILE_NAME}**")
            
            loaded_from_file = True

    # 2. Upload pelo usuário se o DataFrame ainda estiver vazio
    if st.session_state.df_data.empty:
        uploaded_file = st.file_uploader(
            "Selecione o arquivo CSV/Excel com os dados de estoque:",
            type=['csv', 'xlsx', 'xls']
        )
        if uploaded_file:
            # Carrega e processa o arquivo carregado
            df_uploaded, hoje_uploaded = load_and_process_data(uploaded_file)
            if df_uploaded.empty:
                 st.warning("Falha ao processar o arquivo carregado. Tente novamente ou verifique o formato.")
            else:
                # Salva o novo DataFrame no session state e dispara um rerun
                st.session_state.df_data = df_uploaded
                st.session_state.hoje_data = hoje_uploaded
                st.session_state.uploaded_file_name = uploaded_file.name
                st.success(f"Dados carregados com sucesso do arquivo: **{st.session_state.uploaded_file_name}**")
                st.rerun() # Dispara rerun para carregar o dashboard imediatamente
        else:
            st.warning("Por favor, carregue o arquivo de dados CSV ou Excel para iniciar a análise.")

else:
    # Se o DataFrame já estiver carregado na sessão, exibe a mensagem de sucesso e o botão de limpar
    st.success(f"Dados carregados e persistentes do arquivo: **{st.session_state.uploaded_file_name or 'Arquivo Local Padrão'}**")
    st.button("❌ Limpar Dados e Fazer Novo Upload", on_click=clear_data)
    # df e hoje já estão definidos via session_state no início do bloco 'if not df.empty:'
    df = st.session_state.df_data
    hoje = st.session_state.hoje_data


if not df.empty:
   
    # --- Métricas Chave (KPIs) - COM EMOJIS ---
    col1, col2, col3 = st.columns(3)

    total_materiais = df['Material'].nunique()
    media_aging = df['Dias_Em_Estoque'].mean()
    # O cálculo crítico usa df (que é o session_state.df_data)
    criticos_count = df[df['Categoria_Aging'] == 'Crítico'].shape[0]

    with col1:
        st.metric(
            label="📦 Total de Materiais Únicos", # EMOJI
            value=f"{total_materiais}"
        )

    with col2:
        st.metric(
            label="⏳ Média de Aging (Dias)", # EMOJI
            value=f"{media_aging:.1f} dias"
        )

    with col3:
        # A métrica usa a contagem de linhas críticas versus o total de materiais únicos
        percentual_critico = (criticos_count / total_materiais * 100) if total_materiais > 0 else 0
        st.metric(
            label="🚨 Materiais em Risco Crítico (Lotes)", # EMOJI e Clarificação
            value=f"{criticos_count}",
            delta=f"Representa {percentual_critico:.1f}% dos materiais únicos"
        )

    st.divider()

    # --- Filtros (Sidebar) ---
    st.sidebar.header("Filtros de Análise")
    materiais_list = sorted(df['Descricao_Material'].unique())
    selected_materials = st.sidebar.multiselect(
        "Filtrar por Descrição do Material:",
        options=materiais_list,
        default=[]
    )

    # Aplica o filtro
    if selected_materials:
        df_filtered = df[df['Descricao_Material'].isin(selected_materials)]
    else:
        df_filtered = df.copy()
    
    # Recalcula o total de materiais únicos para o info box
    total_materiais_filtrados = df_filtered['Material'].nunique()

    # Exibir a contagem de resultados após o filtro
    st.sidebar.info(f"Mostrando {total_materiais_filtrados} de {total_materiais} materiais únicos.")

    # --- Gráficos do Dashboard ---

    st.header("Análise do aging por Categoria")
    col_chart_1, col_chart_2 = st.columns([1, 2])

    # Gráfico 1: Distribuição Percentual por Categoria (Pizza)
    aging_counts = df_filtered.groupby('Categoria_Aging').agg(
        {'Material': 'nunique'}
    ).reset_index().rename(columns={'Material': 'Contagem_Materiais'})

    # Ordenar as categorias
    category_order = ['Normal', 'Alerta', 'Crítico']
    # Preenche categorias faltantes com 0 para evitar erros no sort/color
    for cat in category_order:
        if cat not in aging_counts['Categoria_Aging'].values:
            aging_counts.loc[len(aging_counts)] = [cat, 0]

    aging_counts['Categoria_Aging'] = pd.Categorical(
        aging_counts['Categoria_Aging'],
        categories=category_order,
        ordered=True
    )
    aging_counts.sort_values('Categoria_Aging', inplace=True)

    # Mapear cores para o gráfico de pizza
    color_map = {'Normal': 'green', 'Alerta': 'orange', 'Crítico': 'red'}
    # Remove linhas com contagem zero para o gráfico de pizza (evita slice invisível)
    aging_counts_display = aging_counts[aging_counts['Contagem_Materiais'] > 0]


    with col_chart_1:
        fig_pie = px.pie(
            aging_counts_display,
            values='Contagem_Materiais',
            names='Categoria_Aging',
            title='Percentual de Materiais por Status de Aging',
            color='Categoria_Aging',
            color_discrete_map=color_map,
            hole=.3
        )
        fig_pie.update_traces(textinfo='percent+label')
        st.plotly_chart(fig_pie, use_container_width=True)

    # Gráfico 2: Top N Materiais com Maior Aging Médio
    top_n = st.slider("Selecione o Top N de Materiais a Exibir:", min_value=5, max_value=20, value=10)

    aging_por_material = df_filtered.groupby(['Material', 'Descricao_Material']).agg(
        Aging_Medio=('Dias_Em_Estoque', 'mean'),
        Total_Lotes=('Lote', 'nunique'),
        Estoque_Total=('Estoque_Disponivel', 'sum')
    ).reset_index().sort_values('Aging_Medio', ascending=False).head(top_n)

    with col_chart_2:
        fig_bar = px.bar(
            aging_por_material,
            y='Descricao_Material',
            x='Aging_Medio',
            color='Aging_Medio',
            color_continuous_scale=px.colors.sequential.Sunset,
            title=f'Top {top_n} Materiais por Aging Médio (Dias)',
            orientation='h'
        )
        fig_bar.update_yaxes(title='Material', automargin=True)
        fig_bar.update_xaxes(title='Aging Médio (Dias)')
        st.plotly_chart(fig_bar, use_container_width=True)

    st.divider()
    st.header("Tabela Detalhada dos Dados do Aging - Pesagem")
    st.write("Dados referente ao depósito PES - Pesagem")

    # Tabela detalhada
    # Selecionar e formatar colunas para a tabela
    df_display = df_filtered[[
        'Material', 'Descricao_Material', 'Lote', 'Estoque_Disponivel', 'UMB',
        'Ultimo_Movimento', 'Dias_Em_Estoque', 'Categoria_Aging'
    ]].copy()

    df_display.rename(columns={
        'Material': 'Cód. Material',
        'Descricao_Material': 'Descrição',
        'Lote': 'Lote',
        'Estoque_Disponivel': 'Estoque',
        'UMB': 'UM',
        'Ultimo_Movimento': 'Último Movimento',
        'Dias_Em_Estoque': 'Aging (Dias)',
        'Categoria_Aging': 'Status'
    }, inplace=True)

    # Formatação da data
    df_display['Último Movimento'] = df_display['Último Movimento'].dt.strftime('%d/%m/%Y')

    # Aplicar cores de fundo na coluna Status
    def color_status(val):
        color = 'green'
        if val == 'Crítico':
            color = "#b64c55"
        elif val == 'Alerta':
            color = "#f3d572"
        return f'background-color: {color}'

    # --- Função para formatar o número no padrão brasileiro ---
    def format_br_estoque(val):
        """Formata valor para 3 casas decimais, usando '.' para milhar e ',' para decimal."""
        if pd.isna(val):
            return ""
        # 1. Formata para o padrão US (ex: 12345.678 -> '12,345.678')
        us_format = f"{val:,.3f}"
        # 2. Inverte os separadores para o padrão brasileiro
        # Substitui vírgula (milhar US) por 'X' temporário
        step1 = us_format.replace(',', 'X')
        # Substitui ponto (decimal US) por vírgula (decimal BR)
        step2 = step1.replace('.', ',')
        # Substitui 'X' temporário por ponto (milhar BR)
        return step2.replace('X', '.')

    # Definir formato para a coluna 'Estoque' (3 casas decimais, separador decimal = vírgula)
    formatters = {
        'Estoque': format_br_estoque
    }
    
    # Aplicar formatação e cor
    styled_df = df_display.style.applymap(color_status, subset=['Status']).format(formatters)

    st.dataframe(
        styled_df,
        use_container_width=True,
        hide_index=True
    )
