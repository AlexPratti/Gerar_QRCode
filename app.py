import streamlit as st
from docx import Document
from supabase import create_client
import pandas as pd
import re

# Conexão segura
supabase = create_client(st.secrets["URL_SUPABASE"], st.secrets["KEY_SUPABASE"])

def process_docx(file):
    doc = Document(file)
    data = []
    
    # 1. Lista de Seções Conhecidas (Baseado no seu PDF)
    # Isso garante que mesmo que o Word esteja "sujo", o código saiba o que procurar
    secoes_alvo = [
        "ORANTES", "INICIAIS E FINAIS", "PERDÃO", "GLÓRIA", 
        "DEUS NOS FALA", "SALMO", "ACLAMAÇÃO", "OFERTÓRIO", 
        "LOUVOR", "SANTO", "CORDEIRO", "PAZ", "COMUNHÃO", 
        "BÍBLIA", "CRUZ", "LADAINHAS – SEQUÊNCIAS - PROCLAMAÇÕES", 
        "MARIA", "PRECES"
    ]

    current_cat = "GERAL"
    current_hino = None
    current_text = []

    # Regex para hinos (Ex: "1. ", "10. ")
    re_hino = re.compile(r'^\d+[\.\)]\s+')

    for para in doc.paragraphs:
        text = para.text.strip()
        
        # Ignora linhas vazias, números de página isolados ou sumário
        if not text or "...." in text or text.lower() == "sumário":
            continue

        # A. TESTA SE É UMA SEÇÃO (Nível 1)
        # Verifica se o texto da linha é exatamente uma das seções da nossa lista
        if text.upper() in secoes_alvo:
            current_cat = text.upper()
            continue

        # B. TESTA SE É UM HINO (Nível 2)
        if re_hino.match(text):
            if current_hino:
                data.append({"n1": current_cat, "n2": current_hino, "texto": "\n".join(current_text)})
            current_hino = text
            current_text = []
            continue

        # C. CAPTURA O CONTEÚDO
        if current_hino:
            current_text.append(text)

    # Salva o último hino
    if current_hino:
        data.append({"n1": current_cat, "n2": current_hino, "texto": "\n".join(current_text)})
    
    return data

def save_to_db(data):
    # Limpa dados antigos
    supabase.table("hinos_conteudos").delete().neq("id", 0).execute()
    supabase.table("hinos_categorias").delete().neq("id", 0).execute()
    
    seen_cats = {}
    for item in data:
        cat_name = item['n1']
        if cat_name not in seen_cats:
            res = supabase.table("hinos_categorias").insert({"nome_nivel1": cat_name}).execute()
            if res.data:
                seen_cats[cat_name] = res.data[0]['id']
        
        if cat_name in seen_cats:
            supabase.table("hinos_conteudos").insert({
                "categoria_id": seen_cats[cat_name],
                "nome_nivel2": item['n2'],
                "texto_completo": item['texto']
            }).execute()

# --- INTERFACE ---
st.set_page_config(page_title="Hinário Litúrgico", layout="wide")

with st.sidebar:
    st.title("⚙️ Sistema")
    arquivo = st.file_uploader("Upload Hinário (.docx)", type="docx")
    if st.button("🚀 Processar Tudo"):
        if arquivo:
            with st.spinner("Reconstruindo Hinário..."):
                dados = process_docx(arquivo)
                save_to_db(dados)
                st.success(f"Sucesso! {len(dados)} hinos organizados.")
                st.rerun()

# --- EXIBIÇÃO ---
try:
    res_cat = supabase.table("hinos_categorias").select("*").order("id").execute()
    if res_cat.data:
        df_cat = pd.DataFrame(res_cat.data)
        
        col_menu, col_texto = st.columns([1, 2])
        
        with col_menu:
            escolha_n1 = st.selectbox("📌 Selecione a Seção:", df_cat['nome_nivel1'])
            cat_id = int(df_cat[df_cat['nome_nivel1'] == escolha_n1]['id'].iloc[0])
            
            busca = st.text_input("🔍 Busca por nome/número:")
            
            # Puxa hinos da categoria
            hinos_db = supabase.table("hinos_conteudos").select("*").eq("categoria_id", cat_id).order("id").execute().data
            
            if hinos_db:
                if busca:
                    hinos_db = [h for h in hinos_db if busca.lower() in h['nome_nivel2'].lower()]
                
                nomes = [h['nome_nivel2'] for h in hinos_db]
                if nomes:
                    hino_radio = st.radio("📑 Lista de Hinos:", nomes)
                    hino_atual = next(h for h in hinos_db if h['nome_nivel2'] == hino_radio)
                    
                    with col_texto:
                        st.subheader(hino_atual['nome_nivel2'])
                        st.divider()
                        st.text(hino_atual['texto_completo'])
                else:
                    st.warning("Nenhum hino encontrado.")
    else:
        st.info("💡 App pronto. Suba o arquivo Word no menu lateral para começar.")

except Exception as e:
    st.error(f"Erro no sistema: {e}")

