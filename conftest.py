"""
Configuração global do pytest.

Adiciona o diretório raiz ao sys.path para que os módulos em src/
possam ser importados como 'src.ingest', 'src.search', etc.
"""

import sys
import os

# Garante que o diretório raiz do projeto esteja no path de importação,
# permitindo que os testes importem módulos com o prefixo 'src.'
sys.path.insert(0, os.path.dirname(__file__))
