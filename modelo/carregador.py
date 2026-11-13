"""Lê a eleição de um arquivo JSON e monta os objetos do modelo."""

import json
from pathlib import Path

from .candidato import Candidato, Vice
from .cargo import Cargo
from .eleicao import Eleicao, Secao
from .partido import Partido
from .pessoas import Eleitor, Mesario


class CarregadorEleicao:
    """Transforma o arquivo dados/eleicao.json em um objeto Eleicao."""

    def __init__(self, caminho):
        self.__caminho = Path(caminho)

    def carregar(self):
        dados = json.loads(self.__caminho.read_text(encoding="utf-8"))
        partidos = self.__criar_partidos(dados["partidos"])
        cargos = [self.__criar_cargo(c, partidos) for c in dados["cargos"]]
        eleitores = [
            Eleitor(e["titulo"], e["nome"], e.get("biometria", True)) for e in dados["eleitores"]
        ]
        s, e, mesa = dados["secao"], dados["eleicao"], dados["mesa"]
        secao = Secao(s["uf"], s["municipio"], s["zona"], s["secao"], s["local"], s["codigo_urna"])
        return Eleicao(
            e["descricao"], e["turno"], e["data"], secao, partidos, cargos, eleitores,
            Mesario(mesa["presidente"], mesa["senha"]),
        )

    def __criar_partidos(self, lista):
        partidos = {}
        for p in lista:
            partido = Partido(p["numero"], p["sigla"], p["nome"], p.get("cor", "#777777"))
            partidos[partido.numero] = partido
        return partidos

    def __criar_cargo(self, dados, partidos):
        cargo = Cargo(
            dados["codigo"], dados["nome"], dados["digitos"], partidos,
            proporcional=dados.get("proporcional", False),
            votos_por_eleitor=dados.get("votos_por_eleitor", 1),
        )
        for cand in dados["candidatos"]:
            numero = str(cand["numero"])
            partido = partidos.get(numero[:2])
            if partido is None:
                raise ValueError(f"Candidato {numero}: partido {numero[:2]} não cadastrado.")
            vices = [Vice(v["titulo"], v["nome"]) for v in cand.get("vices", [])]
            cargo.adicionar_candidato(Candidato(numero, cand["nome"], partido, vices))
        return cargo
