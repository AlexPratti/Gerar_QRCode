import streamlit as st
import pdfplumber
import re
from supabase import create_client
import io
import base64

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Hinário Visual", layout="wide")

try:
    supabase = create_client(st.secrets["URL_SUPABASE"], st.secrets["KEY_SUPABASE"])
except:
    st.error("Erro de conexão com Supabase.")
    st.stop()

BUCKET = "hinarios"
CATEGORIAS_ALVO = ["ORANTES", "INICIAIS E FINAIS", "PERDÃO", "GLÓRIA", "DEUS NOS FALA", "SALMO", "ACLAMAÇÃO", "OFERTÓRIO", "LOUVOR", "SANTO", "CORDEIRO", "PAZ", "COMUNHÃO", "BÍBLIA", "CRUZ", "LADAINHAS – SEQUÊNCIAS - PROCLAMAÇÕES", "MARIA", "HINOS DIVERSOS", "PRECES"]

def process_and_upload_images(file_bytes):
    """Abre o PDF, recorta hinos e salva cada um como imagem no Storage"""
    try:
        # Limpa banco e storage de imagens antigas
        supabase.table("hinos_conteudos").delete().neq("id", 0).execute()
        supabase.table("hinos_categorias").delete().neq("id", 0).execute()
        
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            progresso = st.progress(0)
            current_cat = "Sem Categoria"
            cat_map = {}

            # Primeiro, cria as categorias no banco e mapeia IDs
            for cat in CATEGORIAS_ALVO:
                res = supabase.table("hinos_categorias").insert({"nome_nivel1": cat}).execute()
                if res.data: cat_map[cat] = res.data[0]['id']

            total = len(pdf.pages)
            for i, page in enumerate(pdf.pages):
                text_lines = page.extract_text_lines()
                if not text_lines: continue

                for idx, line in enumerate(text_lines):
                    t_limpo = line['text'].strip()
                    
                    # Identifica Categoria
                    if t_limpo.upper() in CATEGORIAS_ALVO:
                        current_cat = t_limpo.upper()
                    
                    # Identifica Hino (Número seguido de ponto)
                    elif re.match(r'^\d+\.', t_limpo) and t_limpo == t_limpo.upper():
                        y_ini = line['top']
                        y_fim = page.height

                        # Acha o fim do hino (próxima linha que seja título ou categoria)
                        for next_line in text_lines[idx+1:]:
                            nt = next_line['text'].strip()
                            if re.match(r'^\d+\.', nt) or nt.upper() in CATEGORIAS_ALVO:
                                y_fim = next_line['top']
                                break
                        
                        # Recorta e gera imagem
                        img = page.crop((0, max(0, y_ini-10), page.width, y_fim)).to_image(resolution=200).original
                        img_byte_arr = io.BytesIO()
                        img.save(img_byte_arr, format='PNG')
                        
                        # Nome único para a imagem no Storage
                        img_name = f"hino_{re.sub(r'\W+', '', t_limpo)}.png"
                        
                        # Sobe imagem para o Storage
                        supabase.storage.from_(BUCKET).upload(
                            path=img_name, 
                            file=img_byte_arr.getvalue(), 
                            file_options={"x-upsert": "true", "content-type": "image/png"}
                        )

                        # Salva referência no Banco (campo 'texto_completo' guarda o nome da imagem)
                        if current_cat in cat_map:
                            supabase.table("hinos_conteudos").insert({
                                "categoria_id": cat_map[current_cat],
                                "nome_nivel2": t_limpo,
                                "texto_completo": img_name
                            }).execute()

                progresso.progress((i + 1) / total)
        return True
    except Exception as e:
        st.error(f"Erro no processamento radical: {e}")
        return False

# --- INTERFACE ---
with st.expander("⬆️ Upload Novo Hinário"):
    novo = st.file_uploader("Selecione o PDF", type="pdf")
    if st.button("Processar Tudo") and novo:
        if process_and_upload_images(novo.read()):
            st.success("Hinário processado e hinos convertidos em imagens!")
            st.rerun()

# --- EXIBIÇÃO ---
try:
    res_cat = supabase.table("hinos_categorias").select("*").order("nome_nivel1").execute()
    if res_cat.data:
        cats = {c['nome_nivel1']: c['id'] for c in res_cat.data}
        col1, col2 = st.columns(2)
        
        with col1:
            sel_cat = st.selectbox("Categoria", list(cats.keys()))
        
        hinos = supabase.table("hinos_conteudos").select("*").eq("categoria_id", cats[sel_cat]).execute().data
        if hinos:
            # Ordenação numérica
            hinos_ord = sorted(hinos, key=lambda x: int(re.search(r'\d+', x['nome_nivel2']).group()) if re.search(r'\d+', x['nome_nivel2']) else 0)
            titulos = [h['nome_nivel2'] for h in hinos_ord]
            
            with col2:
                sel_hino = st.selectbox("Hino", titulos)
            
            # Pega o nome da imagem salva no banco
            hino_obj = next(h for h in hinos if h['nome_nivel2'] == sel_hino)
            img_path = hino_obj['texto_completo']

            # EXIBIÇÃO DA IMAGEM (Sem abrir PDF!)
            img_url = supabase.storage.from_(BUCKET).get_public_url(img_path)
            st.markdown(f'''
                <div style="background:white; padding:10px; border-radius:10px; text-align:center;">
                    <img src="{img_url}" style="max-width:100%; height:auto; border:1px solid #eee;">
                </div>
            ''', unsafe_allow_html=True)
except Exception as e:
    st.info("Aguardando upload e processamento...")
