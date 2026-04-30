import os

def mapear_projeto_limpo():
    caminho_base = os.path.dirname(os.path.abspath(__file__))
    arquivo_saida = os.path.join(caminho_base, "estrutura_projeto.txt")
    
    # --- LISTA DE IGNORADOS ---
    # Adicione aqui nomes de pastas ou arquivos que você não quer ver no relatório
    pastas_ignoradas = {
        '.git', '__pycache__', 'venv', '.venv', 'env', 
        '.pytest_cache', '.vscode', '.idea', 'node_modules'
    }
    arquivos_ignorados = {
        'estrutura_projeto.txt', os.path.basename(__file__), 
        '.DS_Store', 'desktop.ini'
    }

    with open(arquivo_saida, "w", encoding="utf-8") as f:
        f.write(f"ESTRUTURA DO PROJETO: {os.path.basename(caminho_base)}\n")
        f.write("=" * 60 + "\n\n")
        
        for raiz, pastas, arquivos in os.walk(caminho_base):
            # 1. Filtra as pastas para o os.walk não "entrar" nelas
            pastas[:] = [p for p in pastas if p not in pastas_ignoradas]
            
            nivel = raiz.replace(caminho_base, '').count(os.sep)
            indentacao = '    ' * nivel
            
            # Escreve a pasta atual
            nome_pasta = os.path.basename(raiz)
            if raiz == caminho_base:
                f.write(f"[Raiz] {nome_pasta}/\n")
            else:
                f.write(f"{indentacao}[Pasta] {nome_pasta}/\n")
            
            # Escreve os arquivos (filtrados)
            sub_indentacao = '    ' * (nivel + 1)
            for arquivo in arquivos:
                if arquivo not in arquivos_ignorados and not arquivo.endswith(('.pyc', '.pyo')):
                    f.write(f"{sub_indentacao}- {arquivo}\n")
        
    print(f"Mapeamento limpo concluído! Arquivo gerado: estrutura_projeto.txt")

if __name__ == "__main__":
    mapear_projeto_limpo()