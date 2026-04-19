import streamlit as st
from docx import Document
from supabase import create_client
import pandas as pd

# Conexão com os nomes que você definiu no Secrets
url = st.secrets["URL_SUPABASE"]
key = st.secrets["KEY_SUPABASE"]
supabase = create_client(url, key)

def process_docx(file):
    doc = Document(file)
    data = []
    current_n1 = None
    for para in doc.paragraphs:
        style = para.style.name
        # Identifica Títulos 1 e 2 (ajuste conforme o idioma do seu Word)
        if 'Heading 1' in style or 'Título 1' in style:
            current_n1 = para.text.strip()
        elif ('Heading 2' in style or 'Título 2' in style) and current_n1:
            data.append({"n1": current_n1, "n2": para.text.strip()})
    return data

def save_to_db(data):
    # Limpa as tabelas existentes (Sobrepõe o arquivo)
    # Importante: a ordem de delete evita erro de chave estrangeira
    supabase.table("hinos_conteudos").delete().neq("id", 0).execute()
    supabase.table("hinos_categorias").delete().neq("id", 0).execute()
    
    categorias_unicas = sorted(list(set([item['n1'] for item in data])))
    for cat in categorias_unicas:
        res = supabase.table("hinos_categorias").insert({"nome_nivel1": cat}).execute()
        cat_id = res.data[0]['id']
        
        itens = [
            {"categoria_id": cat_id, "nome_nivel2": item['n2']} 
            for item in data if item['n1'] == cat
        ]
        if itens:
            supabase.table("hinos_conteudos").insert(itens).execute()

# --- Interface ---
st.set_page_config(page_title="Hinos Litúrgicos", layout="wide")
st.title("📖 Hinário Litúrgico")

# Área de Upload (oculta por padrão para não ocupar tela)
with st.expander("⬆️ Upload de novo arquivo (.docx)"):
    arquivo = st.file_uploader("Isso substituirá todos os hinos atuais", type="docx")
    if st.button("Confirmar Processamento"):
        if arquivo:
            with st.spinner("Processando..."):
                dados = process_docx(arquivo)
                save_to_db(dados)
                st.success("Banco de dados atualizado com sucesso!")
                st.rerun()

# Carregamento de Dados
try:
    res_cat = supabase.table("hinos_categorias").select("id, nome_nivel1").order("nome_nivel1").execute()
    
    if res_cat.data:
        df_cat = pd.DataFrame(res_cat.data)
        
        col1, col2 = st.columns([1, 1])
        with col1:
            cat_selecionada = st.selectbox("1. Selecione a Categoria:", df_cat['nome_nivel1'])
            cat_id = int(df_cat[df_cat['nome_nivel1'] == cat_selecionada]['id'].iloc[0])
        
        with col2:
            busca = st.text_input("2. 🔍 Filtrar Título (Nível 2):", placeholder="Digite uma palavra-chave...")

        # Busca hinos vinculados à categoria
        query = supabase.table("hinos_conteudos").select("nome_nivel2").eq("categoria_id", cat_id).order("nome_nivel2")
        
        if busca:
            query = query.ilike("nome_nivel2", f"%{busca}%")
        
        res_hinos = query.execute()
        
        if res_hinos.data:
            hinos_lista = [h['nome_nivel2'] for h in res_hinos.data]
            st.markdown(f"### Lista de hinos em: **{cat_selecionada}**")
            # Radio button para o usuário escolher o hino final
            escolha_final = st.radio("Selecione para visualizar:", hinos_lista, label_visibility="collapsed")
            
            if escolha_final:
                st.info(f"Você selecionou: **{escolha_final}**")
        else:
            st.warning("Nenhum título encontrado com este filtro.")
    else:
        st.info("O banco de dados está vazio. Por favor, suba um arquivo docx no menu acima.")

except Exception as e:
    st.error(f"Erro ao conectar ao banco: {e}")
