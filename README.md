# # 3D-terminal

Terminal avanzado para impresoras 3D basadas en firmware Marlin, con interfaz gráfica en PyQt6 y control directo por puerto serie.

## Características

- Consola interactiva para comandos G-code.
- Carga y envío de archivos G-code.
- Control manual de ejes, extrusión y velocidades.
- Visualización de temperaturas de hotend y cama.
- Preajustes de precalentado PLA y ABS.
- Control de ventilador.
- Barra de progreso de impresión.
- Modo oscuro opcional.
- Configuración de puerto, baudrate y conexión/desconexión rápida.

## seguridad 
hay secciones donde el acceso va a estar restringido por una contraseña ese bloqueo va a estar implementado en lugares precisos o comandos que puedan causar daño a los equipos el código 
                   4657

## Instalación

Necesitas Python 3.8+ y las siguientes dependencias:

```bash
pip install pyqt6 pyserial