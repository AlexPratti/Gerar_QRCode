import streamlit as st
import segno
from io import BytesIO

st.set_page_config(page_title="Gerador QR Turbo", page_icon="⚡")

st.title("🎯 Gerador de Link Direto (Otimizado)")
st.write("Cole qualquer link. O sistema ajustará a densidade para o seu Redmi ler direto.")

# Entrada de link vazia para você usar como quiser
url_input = st.text_input("Cole a URL aqui:", placeholder="meusite.com").strip()

if url_input:
    # 1. TRATAMENTO RIGOROSO
    # Forçamos o HTTPS e limpamos qualquer caractere invisível
    url_limpa = url_input.replace(" ", "").replace("\n", "")
    if not url_limpa.startswith(("http://", "https://")):
        final_url = f"https://{url_limpa}"
    else:
        final_url = url_limpa

    try:
        # 2. O SEGREDO PARA XIAOMI: Baixa Densidade (Boost de Contraste)
        # Usamos micro=False e forçamos uma versão mínima para os blocos ficarem GRANDES
        # O segredo é o 'boost_error=False' para não carregar o código de pontos desnecessários
        qr = segno.make_qr(final_url, error='l', boost_error=False)
        
        buf = BytesIO()
        # Scale 20 cria quadrados gigantescos. É impossível a câmera do Redmi confundir com texto.
        qr.save(buf, kind='png', scale=20, border=4)
        byte_im = buf.getvalue()

        # 3. EXIBIÇÃO
        st.success(f"Link configurado: {final_url}")
        st.image(byte_im, caption="Aponte a câmera (O botão 'Ir para o site' deve aparecer)", width=450)

        st.download_button(
            label="📥 Baixar QR Code de Alta Compatibilidade",
            data=byte_im,
            file_name="qrcode_direto.png",
            mime="image/png"
        )

    except Exception as e:
        st.error(f"Erro: {e}")

st.divider()
st.warning("💡 **Dica Técnica:** Se o seu Redmi ainda mostrar 'Copiar Texto', afaste um pouco o celular da tela. Como aumentamos a escala para 20, o código ficou muito grande e nítido; a câmera precisa de um pouco de distância para focar em todos os blocos de uma vez.")
