"""Sons da urna, gerados por código (não precisa de arquivos de áudio)."""

import math
import struct
import tempfile
import wave
from pathlib import Path

from PySide6.QtCore import QUrl

try:
    from PySide6.QtMultimedia import QSoundEffect
except ImportError:  # módulo de áudio indisponível: o simulador funciona sem som
    QSoundEffect = None


class Sons:
    """Toca os bipes da urna e do terminal. Use Sons(ativo=False) para silenciar."""

    TAXA = 44100
    # Cada som é uma sequência de (frequência em Hz, duração em s). Frequência 0 = silêncio.
    SEQUENCIAS = {
        "tecla": [(1040, 0.07)],
        "confirma": [(1040, 0.06), (0, 0.03), (1040, 0.06), (0, 0.03), (1250, 0.10)],
        "fim": [(1250, 0.09), (0, 0.05)] * 4 + [(1250, 0.60)],
        "erro": [(320, 0.22)],
        "liberado": [(880, 0.08), (0, 0.05), (1180, 0.12)],
    }

    def __init__(self, ativo=True):
        self.__efeitos = {}
        if not ativo or QSoundEffect is None:
            return
        pasta = Path(tempfile.gettempdir()) / "simulador_urna_sons"
        pasta.mkdir(exist_ok=True)
        for nome, sequencia in self.SEQUENCIAS.items():
            caminho = pasta / f"{nome}.wav"
            if not caminho.exists():
                self.__gerar_wav(caminho, sequencia)
            efeito = QSoundEffect()
            efeito.setSource(QUrl.fromLocalFile(str(caminho)))
            efeito.setVolume(0.7)
            self.__efeitos[nome] = efeito

    @property
    def disponiveis(self):
        return sorted(self.__efeitos)

    def tocar(self, nome):
        efeito = self.__efeitos.get(nome)
        if efeito is not None:
            efeito.stop()
            efeito.play()

    def __gerar_wav(self, caminho, sequencia, volume=0.45):
        """Sintetiza os bipes (onda senoidal com rampa) e grava um arquivo .wav."""
        amostras = []
        for freq, dur in sequencia:
            n = int(self.TAXA * dur)
            borda = int(self.TAXA * 0.005)  # 5 ms de rampa para não estalar
            for i in range(n):
                if freq == 0:
                    amostras.append(0)
                    continue
                env = min(1.0, i / borda, (n - i) / borda)
                valor = math.sin(2 * math.pi * freq * i / self.TAXA)
                onda = 0.8 * valor + 0.2 * (1 if valor >= 0 else -1)  # timbre de bipe
                amostras.append(int(32767 * volume * env * onda))
        with wave.open(str(caminho), "wb") as arq:
            arq.setnchannels(1)
            arq.setsampwidth(2)
            arq.setframerate(self.TAXA)
            arq.writeframes(struct.pack(f"<{len(amostras)}h", *amostras))
