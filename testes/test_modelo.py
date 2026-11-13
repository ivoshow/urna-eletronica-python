"""Testes das regras da urna (rodar na pasta simulador_urna):

    python -m unittest discover -s testes -t .
"""

import unittest
from pathlib import Path

from modelo.carregador import CarregadorEleicao
from modelo.cargo import TipoVoto
from modelo.erros import (
    BiometriaPendente, EleitorJaVotou, EleitorNaoEncontrado, OperacaoInvalida, SenhaIncorreta,
    UrnaBloqueada, UrnaDesconectada, UrnaOcupada, VotacaoNaoIniciada,
)
from modelo.terminal import TerminalMesario
from modelo.urna import EstadoUrna, Urna

DADOS = Path(__file__).resolve().parent.parent / "dados" / "eleicao.json"
DADOS_2TURNO = DADOS.with_name("eleicao_2turno.json")
JOAO, PEDRO, MARIA, ANA = "000123450101", "000345670303", "000234560202", "000456780404"


class TestUrna(unittest.TestCase):
    def setUp(self):
        self.eleicao = CarregadorEleicao(DADOS).carregar()
        self.urna = Urna(self.eleicao)
        self.terminal = TerminalMesario(self.eleicao)

    def abrir(self):
        self.terminal.conectar(self.urna)
        self.terminal.abrir_votacao("1234")

    def votar(self, *numeros):
        """Digita e confirma cada número ("B" = branco)."""
        for numero in numeros:
            if numero == "B":
                self.urna.votar_branco()
            else:
                for d in numero:
                    self.urna.digitar(d)
            self.assertIsNotNone(self.urna.confirmar(), f"não confirmou {numero}")

    def test_sem_cabo_nao_libera(self):
        with self.assertRaises(UrnaDesconectada):
            self.terminal.abrir_votacao("1234")
        self.abrir()
        self.terminal.desconectar()
        eleitor = self.terminal.consultar(ANA)
        with self.assertRaises(UrnaDesconectada):
            self.terminal.liberar(eleitor, digital_conferida=True)

    def test_teclado_bloqueado_sem_liberacao(self):
        with self.assertRaises(UrnaBloqueada):
            self.urna.digitar("1")
        self.abrir()
        with self.assertRaises(UrnaBloqueada):
            self.urna.confirmar()

    def test_abertura_exige_senha(self):
        self.terminal.conectar(self.urna)
        with self.assertRaises(SenhaIncorreta):
            self.terminal.abrir_votacao("0000")
        self.assertIs(self.urna.estado, EstadoUrna.PREPARADA)   # continua fechada
        self.assertIsNone(self.urna.zeresima)                    # nem emitiu a zerésima
        self.assertIn("Tentativa de abertura com senha incorreta", [m for _, m in self.urna.log])
        self.terminal.abrir_votacao("1234")
        self.assertIs(self.urna.estado, EstadoUrna.AGUARDANDO_ELEITOR)

    def test_votacao_nao_iniciada(self):
        self.terminal.conectar(self.urna)
        with self.assertRaises(VotacaoNaoIniciada):
            self.terminal.verificar_urna_pronta()

    def test_biometria_e_titulo(self):
        self.abrir()
        with self.assertRaises(EleitorNaoEncontrado):
            self.terminal.consultar("999999999999")
        joao = self.terminal.consultar(JOAO)
        with self.assertRaises(BiometriaPendente):
            self.terminal.liberar(joao)
        self.terminal.liberar(joao, digital_conferida=True)
        self.assertIs(self.urna.estado, EstadoUrna.VOTANDO)
        with self.assertRaises(UrnaOcupada):
            self.terminal.liberar(self.terminal.consultar(ANA), digital_conferida=True)

    def test_sem_biometria_vota_com_documento(self):
        self.abrir()
        pedro = self.terminal.consultar(PEDRO)          # sem biometria cadastrada
        self.assertFalse(pedro.possui_biometria)
        self.terminal.liberar(pedro)                     # liberado pelo documento com foto
        self.votar("1401", "14100", "141", "277", "14", "14")
        self.assertTrue(pedro.votou)

    def test_interromper_sem_voto_confirmado_suspende(self):
        self.abrir()
        ana = self.terminal.consultar(ANA)
        self.terminal.liberar(ana, digital_conferida=True)
        for d in "14":
            self.urna.digitar(d)                         # digitou, mas não confirmou nada
        with self.assertRaises(SenhaIncorreta):
            self.terminal.interromper_votacao("0000")
        self.assertIs(self.urna.estado, EstadoUrna.VOTANDO)
        r = self.terminal.interromper_votacao("1234")
        self.assertFalse(r.eleitor_votou)
        self.assertFalse(ana.votou)                      # pode voltar e votar depois
        self.assertEqual(sum(c.total for c in self.eleicao.cargos), 0)
        self.terminal.liberar(self.terminal.consultar(ANA), digital_conferida=True)
        self.assertIs(self.urna.estado, EstadoUrna.VOTANDO)

    def test_interromper_com_votos_anula_restantes(self):
        self.abrir()
        ana = self.terminal.consultar(ANA)
        self.terminal.liberar(ana, digital_conferida=True)
        self.votar("1401", "14100")                      # confirmou DF e DE, desistiu no Senado
        r = self.terminal.interromper_votacao("1234")
        self.assertEqual((r.eleitor_votou, r.confirmados, r.anulados), (True, 2, 4))
        self.assertTrue(ana.votou)
        cargos = {c.codigo: c for c in self.eleicao.cargos}
        self.assertEqual(cargos["DF"].buscar("1401").votos, 1)   # confirmados valem
        self.assertEqual(cargos["SE"].nulos, 2)                  # 2 vagas do Senado
        self.assertEqual(cargos["GO"].nulos, 1)
        self.assertEqual(cargos["PR"].nulos, 1)
        for c in self.eleicao.cargos:                            # BU continua fechando
            self.assertEqual(c.total, self.eleicao.comparecimento * c.votos_por_eleitor)
        with self.assertRaises(OperacaoInvalida):
            self.terminal.interromper_votacao("1234")            # ninguém votando

    def test_fluxo_completo_e_boletim(self):
        self.abrir()
        zeresima = self.urna.zeresima
        self.assertIn("ZERÉSIMA", zeresima.texto)

        self.terminal.liberar(self.terminal.consultar(ANA), digital_conferida=True)
        # DF nominal, DE legenda (só o partido), Senado 2 votos, Gov branco, Pres nulo
        self.votar("1401", "51", "141", "277", "B", "99")
        self.assertIs(self.urna.estado, EstadoUrna.AGUARDANDO_ELEITOR)
        with self.assertRaises(EleitorJaVotou):
            self.terminal.consultar(ANA)

        self.terminal.liberar(self.terminal.consultar(MARIA), digital_conferida=True)
        # DE com número inexistente mas partido válido -> legenda
        self.votar("1401", "51777", "383", "B", "14", "27")

        cargos = {c.codigo: c for c in self.eleicao.cargos}
        self.assertEqual(cargos["DF"].buscar("1401").votos, 2)
        self.assertEqual(cargos["DE"].votos_legenda("51"), 2)
        self.assertEqual(cargos["SE"].total, 4)          # 2 votos por eleitor
        self.assertEqual(cargos["SE"].brancos, 1)
        self.assertEqual(cargos["GO"].brancos, 1)
        self.assertEqual(cargos["PR"].nulos, 1)

        with self.assertRaises(SenhaIncorreta):
            self.terminal.encerrar_votacao("0000")
        bu = self.terminal.encerrar_votacao("1234")
        self.assertIs(self.urna.estado, EstadoUrna.ENCERRADA)
        self.assertIn("Comparecimento ...", bu.texto)
        self.assertTrue(bu.verificar())
        self.assertTrue(all(len(l) <= 40 for l in bu.linhas))

    def test_regras_do_teclado(self):
        self.abrir()
        self.terminal.liberar(self.terminal.consultar(ANA), digital_conferida=True)
        sessao = self.urna.sessao
        self.urna.digitar("1")
        self.assertFalse(self.urna.votar_branco())     # BRANCO só com campo vazio
        self.assertIsNone(self.urna.confirmar())       # número incompleto
        self.urna.corrigir()
        self.assertTrue(self.urna.votar_branco())
        self.assertFalse(self.urna.digitar("1"))       # depois do branco não digita
        for d in "99999":
            self.urna.digitar("9")
        self.assertEqual(sessao.numero, "")

    def test_senado_nao_aceita_mesmo_candidato(self):
        self.abrir()
        self.terminal.liberar(self.terminal.consultar(ANA), digital_conferida=True)
        self.votar("1401", "14100", "141")
        for d in "141":
            self.urna.digitar(d)
        previa = self.urna.sessao.previa
        self.assertFalse(previa.pode_confirmar)
        self.assertEqual(previa.aviso, "CANDIDATO JÁ VOTADO")

    def test_segundo_turno_so_presidente(self):
        eleicao = CarregadorEleicao(DADOS_2TURNO).carregar()
        self.assertEqual(eleicao.turno, 2)
        self.assertEqual([c.nome for c in eleicao.cargos], ["Presidente"])
        urna, terminal = Urna(eleicao), TerminalMesario(eleicao)
        terminal.conectar(urna)
        terminal.abrir_votacao("1234")
        for titulo, voto in [(JOAO, "14"), (MARIA, "27"), (ANA, "B"), (PEDRO, "51")]:
            terminal.liberar(terminal.consultar(titulo), digital_conferida=True)
            if voto == "B":
                urna.votar_branco()
            else:
                for d in voto:
                    urna.digitar(d)
            self.assertIsNotNone(urna.confirmar())          # um único CONFIRMA...
            self.assertIs(urna.estado, EstadoUrna.AGUARDANDO_ELEITOR)  # ...e já é FIM
        presidente = eleicao.cargos[0]
        self.assertEqual((presidente.nominais, presidente.brancos, presidente.nulos), (2, 1, 1))
        bu = terminal.encerrar_votacao("1234")
        self.assertIn("2º turno - 25/10/2026", bu.texto)
        self.assertIn("PRESIDENTE", bu.texto)
        self.assertNotIn("GOVERNADOR", bu.texto)
        self.assertTrue(bu.verificar())

    def test_interpretacao(self):
        df = self.eleicao.cargos[0]
        self.assertIs(df.interpretar("14").tipo, TipoVoto.LEGENDA)
        self.assertIs(df.interpretar("1499").tipo, TipoVoto.LEGENDA)
        self.assertIs(df.interpretar("9999").tipo, TipoVoto.NULO)
        self.assertIsNone(df.interpretar("140").tipo)
        gov = self.eleicao.cargos[3]
        self.assertIs(gov.interpretar("51").tipo, TipoVoto.NULO)  # partido sem candidato


if __name__ == "__main__":
    unittest.main()
