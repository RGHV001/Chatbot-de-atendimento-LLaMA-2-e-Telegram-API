import os
from huggingface_hub import hf_hub_download
from llama_cpp import Llama

# Caminho onde o modelo será salvo localmente
MODEL_PATH = "C:/Users/roger/Documents/Faculdade/tcc/Prototipo/v11/chatbot/llama.cpp/models/firefly-llama2-13b-chat.Q4_K_M.gguf"

def load_model():
    """Carrega o modelo TinyLlama usando o Llama.cpp"""
    llm = Llama(model_path=MODEL_PATH, n_ctx=4096)
    return llm


def generate_text(user_prompt):
    """Gera texto a partir do modelo Llama"""
    llm = load_model()

    # Estruturar o prompt para que o modelo entenda o papel de secretária
    structured_prompt = (
        f"Você é uma secretária de um consultório médico. Sua tarefa é responder de maneira clara "
        f"e educada. Não repita a pergunta do usuário. Apenas responda a seguinte mensagem: {user_prompt}."
    )

    try:
        print(f"Prompt enviado ao modelo: {structured_prompt}")  # Log do prompt

        # Gera a resposta com um limite de tokens e tenta parar no fim da sequência
        output = llm(structured_prompt, max_tokens=500, stop=["</s>"])
        
        # Captura a resposta gerada
        generated_text = output['choices'][0]['text'].strip()
        print(f"Tokens gerados: {generated_text}")  # Log do texto gerado

        # Remove qualquer repetição da pergunta no início da resposta
        if generated_text.startswith(user_prompt):
            generated_text = generated_text[len(user_prompt):].strip()

        # Verifica se a resposta está vazia
        response = generated_text or "Desculpe, não consegui entender sua pergunta. Por favor, tente novamente."

    except Exception as e:
        response = f"Desculpe, ocorreu um erro ao processar sua solicitação. Erro: {str(e)}"

    return response


