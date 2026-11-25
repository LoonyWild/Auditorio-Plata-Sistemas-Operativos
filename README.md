# Auditorio Plata — Sistemas Operativos

**Universidad Autónoma de Zacatecas (UAZ)**  
Ingeniería en Computación  
Materia: Sistemas Operativos

## Descripción

Auditorio Plata es una aplicación web para la emisión de boletos digitales de conciertos, desarrollada utilizando Python, Flask, Oracle Database XE y Docker.

El sistema cuenta con seis conciertos y un aforo independiente de 20,000 personas por función.

## Características principales

- Emisión de boletos en PDF con código QR.
- Validación de autenticidad mediante firma HMAC y consulta en Oracle.
- Control de aforo y folios mediante transacciones.
- Cliente spawner para pruebas concurrentes desde varias computadoras.
- Implementación de monitores, semáforos y exclusión mutua.
- Laboratorio de filósofos comensales.
- Experimentos comparativos con y sin sincronización.

## Tecnologías utilizadas

- Python 3.12
- Flask
- Oracle Database XE 21c
- Docker Desktop
- HTML, CSS y JavaScript
- Cloudflare Tunnel

## Ejecución

1. Configurar Oracle XE y ejecutar los scripts SQL de creación del esquema.
2. Copiar `.env.example` a `.env` y configurar las credenciales locales.
3. Iniciar el servidor con:

   `docker compose up -d --build`

4. Abrir `http://localhost:5000` en el navegador.
5. Instalar las dependencias del cliente desde `requirements_cliente.txt`.
6. Ejecutar `spawner.py` para realizar las pruebas de concurrencia.

## Resultados

En una de las pruebas principales se emitieron 100 boletos en 37.062 segundos, cumpliendo el objetivo de realizar 100 solicitudes exitosas en menos de 60 segundos.

El proyecto también fue probado desde tres computadoras mediante una conexión HTTPS temporal.

## Seguridad

El archivo `.env` contiene credenciales privadas y no forma parte del repositorio. El laboratorio de sincronización utiliza un token de autorización.

## Propósito

Proyecto académico para demostrar la aplicación de algoritmos de sincronización, hilos, semáforos, monitores y transacciones en un sistema distribuido.