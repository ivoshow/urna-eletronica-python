"""Testes da queda de energia: a urna religada recupera tudo da memória."""

import json
import tempfile
import unittest
from pathlib import Path

from modelo.carregador import CarregadorEleicao
from modelo.memoria import MemoriaUrna
from modelo.terminal import TerminalMesario
from modelo.urna import EstadoUrna, Urna

DADOS = Path(__file__).resolve().parent.parent / "dados" / "eleicao.json"
ANA, MARIA, PEDRO = "000456780404", "000234560202", "000345670303"


class TestQuedaDeEnergia(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.memoria = MemoriaUrna(Path(self.pasta.name) / "urna.json")
        self.ligar()

    def tearDown(self):
        self.pasta.cleanup()

    def ligar(self):
        """Cria tudo do zero (como ao religar a urna) usando a mesma memória."""
        self.eleicao = CarregadorEleicao(DADOS).carregar()
        self.urna = Urna(self.eleicao, self.memoria)
        self.terminal = TerminalMesario(self.eleicao)
        if self.urna.conectada:
            self.terminal.conectar(self.urna)

    def votar(self, titulo, *numeros, biometria=True):
        self.terminal.liberar(self.terminal.consultar(titulo), digital_conferida=biometria)
        for numero in numeros:
            for d in numero:
                self.urna.digitar(d)
            self.urna.confirmar()

    def contagem(self):
        return {c.codigo: (c.nominais, c.legenda_total, c.brancos, c.nulos) for c in self.eleicao.cargos}

    def test_caderno_e_votos_sobrevivem_a_queda(self):
        self.terminal.conectar(self.urna)
        zeresima = self.terminal.abrir_votacao("1234")
        self.votar(ANA, "1401", "51", "141", "277", "14", "14")
        self.votar(PEDRO, "2710", "27001", "383", "515", "27", "27", biometria=False)
        antes = self.contagem()

        self.ligar()   # ---- queda de energia e religamento

        self.assertTrue(self.urna.recuperada)
        self.assertIs(self.urna.estado, EstadoUrna.AGUARDANDO_ELEITOR)
        self.assertTrue(self.urna.conectada)
        self.assertTrue(self.eleicao.buscar_eleitor(ANA).votou)      # caderno preservado
        self.assertTrue(self.eleicao.buscar_eleitor(PEDRO).votou)
        self.assertFalse(self.eleicao.buscar_eleitor(MARIA).votou)
        self.assertEqual(self.eleicao.comparecimento, 2)
        self.assertEqual(self.contagem(), antes)                      # votos preservados
        self.assertEqual(self.urna.zeresima.codigo, zeresima.codigo)
        self.assertIn("Energia restabelecida: dados recuperados da memória", [m for _, m in self.urna.log])
        # a votação continua normalmente depois da queda
        self.votar(MARIA, "1422", "14555", "141", "383", "38", "51")
        bu = self.terminal.encerrar_votacao("1234")
        self.assertIn("Comparecimento ....................... 3", bu.texto)
        self.assertTrue(bu.verificar())

    def test_queda_com_eleitor_no_meio_da_votacao(self):
        self.terminal.conectar(self.urna)
        self.terminal.abrir_votacao("1234")
        self.votar(ANA, "1401", "14100")          # confirmou 2 de 6 e a energia caiu

        self.ligar()

        r = self.urna.pendencia_na_queda
        self.assertEqual((r.eleitor_votou, r.confirmados, r.anulados), (True, 2, 4))
        self.assertTrue(self.eleicao.buscar_eleitor(ANA).votou)
        for c in self.eleicao.cargos:
            self.assertEqual(c.total, self.eleicao.comparecimento * c.votos_por_eleitor)

    def test_queda_antes_do_primeiro_voto_suspende(self):
        self.terminal.conectar(self.urna)
        self.terminal.abrir_votacao("1234")
        self.terminal.liberar(self.terminal.consultar(ANA), digital_conferida=True)

        self.ligar()

        self.assertFalse(self.urna.pendencia_na_queda.eleitor_votou)
        self.assertFalse(self.eleicao.buscar_eleitor(ANA).votou)     # pode votar de novo
        self.terminal.liberar(self.terminal.consultar(ANA), digital_conferida=True)
        self.assertIs(self.urna.estado, EstadoUrna.VOTANDO)

    def test_urna_encerrada_continua_encerrada(self):
        self.terminal.conectar(self.urna)
        self.terminal.abrir_votacao("1234")
        self.votar(ANA, "1401", "51", "141", "277", "14", "14")
        bu = self.terminal.encerrar_votacao("1234")

        self.ligar()

        self.assertIs(self.urna.estado, EstadoUrna.ENCERRADA)
        self.assertEqual(self.urna.boletim.codigo, bu.codigo)
        self.assertTrue(self.urna.boletim.verificar())

    def test_memoria_do_1o_turno_nao_vaza_para_o_2o(self):
        self.terminal.conectar(self.urna)
        self.terminal.abrir_votacao("1234")
        self.votar(PEDRO, "1401", "14100", "141", "277", "14", "14", biometria=False)
        segundo_turno = CarregadorEleicao(DADOS.with_name("eleicao_2turno.json")).carregar()
        with self.assertRaises(ValueError):                   # turno diferente: recusa
            Urna(segundo_turno, self.memoria)
        self.assertFalse(segundo_turno.buscar_eleitor(PEDRO).votou)

    def test_memoria_nao_liga_eleitor_ao_voto(self):
        self.terminal.conectar(self.urna)
        self.terminal.abrir_votacao("1234")
        self.votar(ANA, "1401", "51", "141", "277", "14", "14")
        dados = json.loads(self.memoria.caminho.read_text(encoding="utf-8"))
        self.assertEqual(set(dados["contagem"]["DF"]), {"candidatos", "legenda", "brancos", "nulos"})
        self.assertNotIn(ANA, json.dumps(dados["contagem"]))         # só contadores
        self.assertIsNone(dados["em_votacao"])


if __name__ == "__main__":
    unittest.main()
