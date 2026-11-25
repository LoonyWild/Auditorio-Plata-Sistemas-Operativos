
import threading
import time
from sincronizacion import MesaFilosofos

mesa = MesaFilosofos(5)
mutex = threading.Lock()

def filosofo(i):
    for ronda in range(3):
        mesa.tomar(i)

        try:
            with mutex:
                print(
                    f"Filosofo {i+1}: COMIENDO "
                    f"(ronda {ronda+1})",
                    flush=True
                )

            time.sleep(0.1)
        finally:
            mesa.soltar(i)

        with mutex:
            print(
                f"Filosofo {i+1}: libero los tenedores",
                flush=True
            )

hilos = []

for i in range(5):
    hilo = threading.Thread(
        target=filosofo,
        args=(i,),
        daemon=True
    )
    hilos.append(hilo)
    hilo.start()

for hilo in hilos:
    hilo.join(timeout=10)

if any(hilo.is_alive() for hilo in hilos):
    print("PRUEBA INCOMPLETA: hay hilos bloqueados")
else:
    print("PRUEBA COMPLETADA: todos terminaron")
