import streamlit as st
import fitz  # PyMuPDF
import re
from supabase import create_client
import pandas as pd
import io

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Hinário Litúrgico", layout="wide")

# Conexão Supabase
try:
    supabase = create_client(st.secrets["URL_SUPABASE"], st.secrets["KEY_SUPABASE"])
except Exception as e:
    st.error(f"Erro de conexão com Supabase: {e}")
    st.stop()

# Configurações Globais
CATEGORIAS_ALVO = ["ORANTES", "INICIAIS E FINAIS", "PERDÃO", "GLÓRIA", "DEUS NOS FALA", "SALMO", "ACLAMAÇÃO", "OFERTÓRIO", "LOUVOR", "SANTO", "CORDEIRO", "PAZ", "COMUNHÃO", "BÍBLIA", "CRUZ", "LADAINHAS – SEQUÊNCIAS - PROCLAMAÇÕES", "MARIA", "HINOS DIVERSOS", "PRECES"]

# --- FUNÇÕES DE PROCESSAMENTO ---

def process_pdf_fitz(file_bytes):
    """Extrai a estrutura de hinos e páginas do PDF usando PyMuPDF"""
    data = []
    current_cat = "Sem Categoria"
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for i in range(len(doc)):
            page = doc[i]
            text = page.get_text()
            if not text: continue
            for line in text.split('\n'):
                t_limpo = line.strip()
                if t_limpo.upper() in CATEGORIAS_ALVO:
                    current_cat = t_limpo.upper()
                elif re.match(r'^\d+\.', t_limpo) and t_limpo == t_limpo.upper():
                    data.append({"n1": current_cat, "n2": t_limpo, "pag": i + 1})
        doc.close()
        return data
    except Exception as e:
        st.error(f"Erro no processamento do PDF: {e}")
        return []

def save_to_db(data, table_cat, table_cont):
    """Limpa e salva os dados nas tabelas especificadas"""
    supabase.table(table_cont).delete().neq("id", 0).execute()
    supabase.table(table_cat).delete().neq("id", 0).execute()
    for cat in CATEGORIAS_ALVO:
        res = supabase.table(table_cat).insert({"nome_nivel1": cat}).execute()
        if res.data:
            res_data = res.data[0] if isinstance(res.data, list) else res.data
            cat_id = res_data['id']
            itens = [{"categoria_id": cat_id, "nome_nivel2": item['n2'], "texto_completo": str(item['pag'])} for item in data if item['n1'] == cat]
            if itens:
                supabase.table(table_cont).insert(itens).execute()

def render_hino_interface(bucket, file_path, table_cat, table_cont, key_suffix):
    """Interface de seleção e exibição de hinos"""
    try:
        res_cat = supabase.table(table_cat).select("*").order("nome_nivel1").execute()
        if res_cat.data:
            df_cat = pd.DataFrame(res_cat.data)
            col1, col2 = st.columns(2)
            with col1:
                sel_cat = st.selectbox("Categoria", df_cat['nome_nivel1'], key=f"cat_{key_suffix}")
                # CORREÇÃO DO ERRO DE INDEXER: Usamos .iloc[0] para pegar o valor escalar
                cat_id = df_cat[df_cat['nome_nivel1'] == sel_cat]['id'].iloc[0]
            
            hinos_res = supabase.table(table_cont).select("*").eq("categoria_id", int(cat_id)).execute().data
            if hinos_res:
                # Ordenação numérica
                hinos_ord = sorted(hinos_res, key=lambda x: int(re.search(r'\d+', x['nome_nivel2']).group()) if re.search(r'\d+', x['nome_nivel2']) else 0)
                with col2:
                    sel_hino = st.selectbox("Hino", [h['nome_nivel2'] for h in hinos_ord], key=f"hino_{key_suffix}")
                
                # Renderização Visual
                pdf_res = supabase.storage.from_(bucket).download(file_path)
                if pdf_res:
                    hino_obj = next(h for h in hinos_res if h['nome_nivel2'] == sel_hino)
                    p_num = int(hino_obj['texto_completo']) - 1
                    
                    doc = fitz.open(stream=pdf_res, filetype="pdf")
                    page = doc[p_num]
                    
                    # Busca coordenadas para recorte
                    text_instances = page.search_for(sel_hino)
                    y_ini = text_instances[0].y0 if text_instances else 0
                    y_fim = page.rect.height
                    
                    # Busca fim do hino (próximo título ou categoria)
                    blocks = page.get_text("blocks")
                    for b in blocks:
                        # b[1] é a coordenada y0 do bloco
                        if b[1] > y_ini + 10:
                            txt_block = b[4].strip()
                            if re.match(r'^\d+\.', txt_block) or txt_block.upper() in CATEGORIAS_ALVO:
                                y_fim = b[1]
                                break

                    # Geração da Imagem (Zoom 2x para nitidez)
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=fitz.Rect(0, max(0, y_ini-15), page.rect.width, y_fim))
                    st.divider()
                    st.image(pix.tobytes("png"), use_container_width=True)
                    doc.close()
            else:
                st.info("Nenhum hino encontrado nesta categoria.")
        else:
            st.info("Banco de dados vazio. Realize o upload na aba de gerenciamento correspondente.")
    except Exception as e:
        st.error(f"Erro na visualização: {e}")

# --- INTERFACE EM ABAS ---
tab_cifras, tab_letras, tab_up_cifras, tab_up_letras = st.tabs([
    "🎸 Hinos com Cifras", 
    "📖 Hinos (Letras)", 
    "⚙️ Upload Cifras", 
    "⚙️ Upload Letras"
])

# ABA 1: VISUALIZAÇÃO CIFRAS
with tab_cifras:
    render_hino_interface("hinarios", "hinario_atual.pdf", "hinos_categorias", "hinos_conteudos", "cifras")

# ABA 2: VISUALIZAÇÃO LETRAS
with tab_letras:
    render_hino_interface("letras", "hinario_letras.pdf", "hinos_categorias_letras", "hinos_conteudos_letras", "letras")

# ABA 3: UPLOAD CIFRAS
with tab_up_cifras:
    st.subheader("Configuração do Hinário com Cifras")
    novo_c = st.file_uploader("Arquivo PDF (Cifras)", type="pdf", key="up_cifras_file")
    if st.button("🚀 Atualizar Cifras", key="btn_cifras") and novo_c:
        with st.spinner("Processando Cifras..."):
            b = novo_c.read()
            try:
                lista = supabase.storage.from_("hinarios").list()
                if lista: supabase.storage.from_("hinarios").remove([f['name'] for f in lista])
            except: pass
            supabase.storage.from_("hinarios").upload(path="hinario_atual.pdf", file=b, file_options={"x-upsert": "true", "content-type": "application/pdf"})
            dados = process_pdf_fitz(b)
            if dados:
                save_to_db(dados, "hinos_categorias", "hinos_conteudos")
                st.success("Cifras atualizadas!")
                st.rerun()

# ABA 4: UPLOAD LETRAS
with tab_up_letras:
    st.subheader("Configuração do Hinário de Letras (Sem Cifras)")
    novo_l = st.file_uploader("Arquivo PDF (Letras)", type="pdf", key="up_letras_file")
    if st.button("🚀 Atualizar Letras", key="btn_letras") and novo_l:
        with st.spinner("Processando Letras..."):
            b = novo_l.read()
            try:
                lista = supabase.storage.from_("letras").list()
                if lista: supabase.storage.from_("letras").remove([f['name'] for f in lista])
            except: pass
            supabase.storage.from_("letras").upload(path="hinario_letras.pdf", file=b, file_options={"x-upsert": "true", "content-type": "application/pdf"})
            dados = process_pdf_fitz(b)
            if dados:
                save_to_db(dados, "hinos_categorias_letras", "hinos_conteudos_letras")
                st.success("Letras atualizadas!")
                st.rerun()
