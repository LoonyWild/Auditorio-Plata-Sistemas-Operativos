"""Primitivas de monitores y filósofos comensales para la práctica de Sistemas Operativos."""
import threading
from contextlib import contextmanager

class MonitorEmision:
    """Monitor Python (Condition): controla el acceso local al pool, no reemplaza FOR UPDATE Oracle."""
    def __init__(self, limite=12):
        self.cond = threading.Condition()
        self.activos = 0
        self.limite = limite

    @contextmanager
    def turno(self):
        with self.cond:
            while self.activos >= self.limite:
                self.cond.wait()
            self.activos += 1
        try:
            yield
        finally:
            with self.cond:
                self.activos -= 1
                self.cond.notify()


class MesaFilosofos:
    """Simulación didáctica de filósofos comensales con monitor y dos tenedores atómicos."""
    def __init__(self, numero=5):
        self.cond = threading.Condition()
        self.tenedores = [False] * numero
        self.numero = numero

    def tomar(self, indice):
        izq, der = indice, (indice + 1) % self.numero
        with self.cond:
            while self.tenedores[izq] or self.tenedores[der]:
                self.cond.wait()
            self.tenedores[izq] = self.tenedores[der] = True

    def soltar(self, indice):
        izq, der = indice, (indice + 1) % self.numero
        with self.cond:
            self.tenedores[izq] = self.tenedores[der] = False
            self.cond.notify_all()

