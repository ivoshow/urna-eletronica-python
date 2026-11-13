"""Memória interna (não volátil) da urna, gravada em disco.

Na urna real, os votos ficam numa memória que não se apaga quando falta energia.
Aqui essa memória é um arquivo JSON: a urna grava a cada evento importante e,
ao ser religada, recupera tudo de lá.
"""

import json
from pathlib import Path


class MemoriaUrna:
    """Lê e grava o estado da urna em um arquivo JSON.

    Guarda só o que a urna real guarda: contadores de votos, quem já votou
    (caderno), horários, documentos emitidos e o log. NUNCA guarda em quem
    cada eleitor votou — o sigilo continua garantido.
    """

    def __init__(self, caminho):
        self.__caminho = Path(caminho)

    @property
    def caminho(self):
        return self.__caminho

    def existe(self):
        return self.__caminho.exists()

    def gravar(self, dados):
        """Grava de forma atômica: escreve num arquivo temporário e depois troca.

        Assim uma "queda" no meio da gravação nunca deixa o arquivo pela metade.
        """
        self.__caminho.parent.mkdir(parents=True, exist_ok=True)
        temporario = self.__caminho.with_suffix(".tmp")
        temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
        temporario.replace(self.__caminho)

    def ler(self):
        return json.loads(self.__caminho.read_text(encoding="utf-8"))

    def apagar(self):
        self.__caminho.unlink(missing_ok=True)
