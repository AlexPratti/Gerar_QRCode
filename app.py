import streamlit as st
import pdfplumber
import re
from supabase import create_client
import pandas as pd

# Conexão original
supabase = create_client(st.secrets["URL_SUPABASE"], st.secrets["KEY_SUPABASE"])

CATEGORIAS_ALVO = [
    "ORANTES", "INICIAIS E FINAIS", "PERDÃO", "GLÓRIA", "DEUS NOS FALA", 
    "SALMO", "ACLAMAÇÃO", "OFERTÓRIO", "LOUVOR", "SANTO", "CORDEIRO", 
    "PAZ", "COMUNHÃO", "BÍBLIA", "CRUZ", "LADAINHAS – SEQUÊNCIAS - PROCLAMAÇÕES", 
    "MARIA", "PRECES"
]

def process_pdf_with_coords(file):
    data = []
    current_n1 = "Sem Categoria"
    current_n2 = None
    
    with pdfplumber.open(file) as pdf:
        progresso = st.progress(0)
        total_pags = len(pdf.pages)
        
        for i, page in enumerate(pdf.pages):
            words = page.extract_words()
            # Extraímos o texto por linhas para identificar os títulos
            linhas_texto = page.extract_text().split('\n')
            
            for texto_linha in linhas_texto:
                texto_limpo = texto_linha.strip()
                
                if texto_limpo.upper() in CATEGORIAS_ALVO:
                    current_n1 = texto_limpo.upper()
                    continue

                # Identifica títulos que começam com "Número."
                if re.match(r'^\d+\.', texto_limpo):
                    # CORREÇÃO DEFINITIVA: Busca a coordenada vertical (top) da primeira palavra do título
                    primeira_parte_titulo = texto_limpo.split()[0]
                    y_top = 0
                    for w in words:
                        if w == primeira_parte_titulo:
                            y_top = float(w['top'])
                            break
                    
                    # Se já havia um hino anterior na mesma página, o fim dele é o início deste
                    if data and data[-1]['pag_fim'] == i + 1:
                        data[-1]['y_fim'] = y_top - 5

                    data.append({
                        "n1": current_n1,
                        "n2": texto_limpo,
                        "pag_inicio": i + 1,
                        "y_ini": y_top - 10 if y_top > 10 else 0,
                        "pag_fim": i + 1,
                        "y_fim": float(page.height) 
                    })
            progresso.progress((i + 1) / total_pags)
    return data
def save_to_db(data):
    # Limpeza original
    supabase.table("hinos_conteudos").delete().neq("id", 0).execute()
    supabase.table("hinos_categorias").delete().neq("id", 0).execute()
    
    for cat_nome in CATEGORIAS_ALVO:
        res = supabase.table("hinos_categorias").insert({"nome_nivel1": cat_nome}).execute()
        if res.data:
            # Pega o ID da categoria criada (Supabase retorna lista)
            cat_id = res.data[0]['id']
            
            itens = [
                {
                    "categoria_id": cat_id, 
                    "nome_nivel2": item['n2'],
                    # Guardamos: pag_ini ; y_ini ; pag_fim ; y_fim
                    "texto_completo": f"{item['pag_inicio']};{item['y_ini']};{item['pag_fim']};{item['y_fim']}"
                } for item in data if item['n1'] == cat_nome
            ]
            if itens:
                supabase.table("hinos_conteudos").insert(itens).execute()

# --- INTERFACE ---
st.set_page_config(page_title="Hinário Litúrgico", layout="wide")

with st.expander("⬆️ Sincronizar Novo PDF"):
    arquivo = st.file_uploader("Selecione o arquivo PDF", type="pdf")
    if st.button("Atualizar Banco de Dados") and arquivo:
        dados = process_pdf_with_coords(arquivo)
        save_to_db(dados)
        st.success("Banco de dados atualizado!")
        st.rerun()

try:
    res_cat = supabase.table("hinos_categorias").select("*").order("nome_nivel1").execute()
    if res_cat.data and arquivo:
        df_cat = pd.DataFrame(res_cat.data)
        c1, c2 = st.columns(2)
        
        with c1:
            escolha_n1 = st.selectbox("Categoria", df_cat['nome_nivel1'], key="c_select")
            id_n1 = int(df_cat[df_cat['nome_nivel1'] == escolha_n1]['id'].iloc[0])
        
        hinos = supabase.table("hinos_conteudos").select("*").eq("categoria_id", id_n1).execute().data
        
        if hinos:
            # Ordenação numérica para o seletor não ficar bagunçado
            hinos_ordenados = sorted(hinos, key=lambda x: int(re.search(r'\d+', x['nome_nivel2']).group()))
            titulos = [h['nome_nivel2'] for h in hinos_ordenados]
            
            # Key dinâmica para resetar a lista ao trocar de categoria
            hino_sel = st.selectbox("Hino:", titulos, key=f"sel_{escolha_n1}")
            
            item = next(h for h in hinos if h['nome_nivel2'] == hino_sel)
            c = item['texto_completo'].split(';')
            p_ini, y_ini, p_fim, y_fim = int(c[0]), float(c[1]), int(c[2]), float(c[3])

            st.divider()
            with pdfplumber.open(arquivo) as pdf:
                page = pdf.pages[p_ini - 1]
                # Realiza o CROP (Recorte vertical): (x0, top, x1, bottom)
                # O crop isola apenas o hino selecionado
                recorte = page.crop((0, y_ini, page.width, y_fim))
                st.image(recorte.to_image(resolution=200).original, use_container_width=True)
    else:
        st.info("Aguardando upload e seleção.")
except Exception as e:
    st.error(f"Erro: {e}")
