import streamlit as st
import pdfplumber
import re
from supabase import create_client
import pandas as pd

# Conexão original mantida
supabase = create_client(st.secrets["URL_SUPABASE"], st.secrets["KEY_SUPABASE"])

# Lista exata definida por você para garantir o Nível 1
CATEGORIAS_ALVO = [
    "ORANTES", "INICIAIS E FINAIS", "PERDÃO", "GLÓRIA", "DEUS NOS FALA", 
    "SALMO", "ACLAMAÇÃO", "OFERTÓRIO", "LOUVOR", "SANTO", "CORDEIRO", 
    "PAZ", "COMUNHÃO", "BÍBLIA", "CRUZ", "LADAINHAS – SEQUÊNCIAS - PROCLAMAÇÕES", 
    "MARIA", "PRECES"
]

def process_pdf(file):
    data = []
    current_n1 = "Sem Categoria"
    current_n2 = None
    current_text = []

    with pdfplumber.open(file) as pdf:
        progresso = st.progress(0)
        total_paginas = len(pdf.pages)
        
        for i, page in enumerate(pdf.pages):
            # O parâmetro layout=True é o que mantém a posição das cifras
            text = page.extract_text(layout=True)
            if not text: continue
            
            linhas = text.split('\n')
            for linha in linhas:
                # Usamos texto_limpo apenas para checagem, mas guardamos a 'linha' com espaços
                texto_limpo = linha.strip()
                
                if not texto_limpo or "Sumário" in texto_limpo: 
                    continue

                # Identifica Nível 1
                if texto_limpo.upper() in CATEGORIAS_ALVO:
                    if current_n2:
                        data.append({"n1": current_n1, "n2": current_n2, "texto": "\n".join(current_text)})
                    current_n1 = texto_limpo.upper()
                    current_n2 = None 
                    current_text = []
                    data.append({"n1": current_n1, "n2": None, "texto": ""})
                    continue

                # Identifica Nível 2 (Inicia com número e ponto)
                if re.match(r'^\d+\.', texto_limpo):
                    if current_n2:
                        data.append({"n1": current_n1, "n2": current_n2, "texto": "\n".join(current_text)})
                    current_n2 = re.sub(r'\s\.+\s\d+$', '', texto_limpo)
                    current_text = []
                    
                # Captura Corpo do Texto e Cifras (Preservando espaços da linha original)
                elif current_n2:
                    if not texto_limpo.isdigit():
                        # Adicionamos a 'linha' e não o 'texto_limpo' para manter o alinhamento
                        current_text.append(linha)

            progresso.progress((i + 1) / total_paginas)

    if current_n2:
        data.append({"n1": current_n1, "n2": current_n2, "texto": "\n".join(current_text)})
        
    return data
def save_to_db(data):
    supabase.table("hinos_conteudos").delete().neq("id", 0).execute()
    supabase.table("hinos_categorias").delete().neq("id", 0).execute()
    
    categorias_encontradas = sorted(list(set([item['n1'] for item in data])))
    
    for cat_nome in categorias_encontradas:
        res = supabase.table("hinos_categorias").insert({"nome_nivel1": cat_nome}).execute()
        cat_id = res.data[0]['id']
        
        itens = [
            {"categoria_id": cat_id, "nome_nivel2": item['n2'], "texto_completo": item['texto']} 
            for item in data if item['n1'] == cat_nome and item['n2'] is not None
        ]
        
        if itens:
            supabase.table("hinos_conteudos").insert(itens).execute()

# --- INTERFACE ---
st.set_page_config(page_title="Hinário Litúrgico", layout="wide")

with st.expander("⬆️ Configurações de Upload (PDF)"):
    arquivo = st.file_uploader("Upload do arquivo PDF", type="pdf")
    if st.button("Atualizar Banco de Dados") and arquivo:
        with st.spinner("Sincronizando..."):
            dados = process_pdf(arquivo)
            save_to_db(dados)
            st.success("Sincronização concluída!")
            st.rerun()

# --- EXIBIÇÃO ---
try:
    res_cat = supabase.table("hinos_categorias").select("*").order("nome_nivel1").execute()
    if res_cat.data:
        df_cat = pd.DataFrame(res_cat.data)
        c1, c2 = st.columns(2)
        with c1:
            escolha_n1 = st.selectbox("Selecione a Categoria", df_cat['nome_nivel1'])
            id_n1 = int(df_cat[df_cat['nome_nivel1'] == escolha_n1]['id'].iloc[0])
        with c2:
            termo = st.text_input("🔍 Buscar hino por nome")

        hinos = supabase.table("hinos_conteudos").select("*").eq("categoria_id", id_n1).ilike("nome_nivel2", f"%{termo}%").execute().data

        if hinos:
            hino_selecionado_nome = st.radio("Escolha o hino para ler:", [h['nome_nivel2'] for h in hinos])
            conteudo_hino = next(h for h in hinos if h['nome_nivel2'] == hino_selecionado_nome)
            
            st.markdown("---")
            st.subheader(conteudo_hino['nome_nivel2'])
            
            # BLOCO DE EXIBIÇÃO FIEL: Usa tag <pre> para manter espaços e cifras no lugar
            st.markdown(f"""
            <div style="background-color: #f9f9f9; padding: 20px; border-radius: 10px; border: 1px solid #ddd;">
                <pre style="font-family: 'Courier New', Courier, monospace; font-size: 14px; white-space: pre-wrap;">{conteudo_hino['texto_completo']}</pre>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.warning("Nenhum hino encontrado nesta categoria.")
except Exception as e:
    st.info("Aguardando upload do primeiro arquivo...")
