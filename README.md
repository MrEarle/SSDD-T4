# IIC2523-T2-G06

IIC2523 - Sistemas Distribuidos - Pontificia Universidad Católica de Chile

## Integrantes

Nombre           | Mail
-------------    | -------------------
Benjamín Earle   | biearle@uc.cl
Christian Eilers | ceilers@uc.cl
Jorge Facuse     | jiperez11@uc.cl
Benjamín Lepe    | balepe@uc.cl
Mauro Mendoza    | msmendoza@uc.cl
Martín Ramírez   | mramirez7@uc.cl

## Environment settings

El **backend** de la aplicación fue desarrollado en Python 3.9. En primer lugar
se recomienda crear un `venv` para almacenar las dependencias de esta parte de
la tarea:

1. Donde gusten, pero una buena opción es el directorio raíz del proyecto, se
crea el `venv`:

```shell
python3 -m virtualenv .venv
```

Y en caso de linux si se tienen problemas con tkinter:

```shell
sudo apt-get install python3-tk
```

2. Se activa el entorno virtual:

Bash/Git Bash:

```shell
source .venv/bin/activate
```

Windows:

```powershell
.venv/Scripts/activate.ps1
```

3. lo actualizan

```shell
pip3 install -U pip setuptools wheel
```

4. y finalmente instalan las dependencias de la tarea:

```shell
pip3 install -r requerimentes.txt
```

## Ejecución

Una vez se han instalado las librerías necesarias, se deben seguir los siguientes pasos:

1. Ejecutar el [DNS](#dns)

```shell
python3 dns.py
```

2. Ejecutar los clientes, el dns se encargará de flagear a los primeros clientes como servidores.

```shell
python3 main.py
```

**NOTA:** Existen otros parámetros opcionales para correr el código principal (no el DNS). A continuación se describen.

- `--dns_ip` y `--dns_port`: En caso de que el DNS esté corriendo en otra máquina, se debe especificar su `ip` y `port` de forma explícita, ya que por defecto esto apunta a `localhost:8000`.
- `--server_uri` o `-u`: Especifica la URI del server. Por defecto esta es `backend.com`.
- `--min_n` o `-n`: Mínima cantidad de clientes para que se comience el servicio de chat. Este valor debe ser incluido en todos los clientes en caso de que sea distinto de 0.

# Descripción proceso tarea 3

## Soporte para múltiples servidores

El DNS ahora mantiene registro de hasta 2 servidores activos. Cuando un cliente pide la dirección asociada a la URI del servidor, el DNS seleccionará la dirección con la IP más cercana al cliente. Esto fue hecho según fue sugerido en el enunciado de la tarea.

## Migración de Servidores

El principal cambio realizado para la migración de los servidores es que, al pedirle al DNS el servidor al cual migrar, este va a elegir uno que no sea servidor activo. Al realizar el cambio, el DNS sobreescribirá la dirección del servidor que está migrando con el nuevo servidor.

## Replicación

Para mantener consistencia orientada al cliente, para cada mensaje, los servidores se comunican con el fin de determinar el índice a asignar para el mensaje. De esta manera, ambos servidores mantienen el orden de los mensajes de forma consistente, garantizando monotonic reads.

# Descripción proceso tarea 2

## Manejo de cliente y servidor en la misma máquina

Al ejecutar el archivo [`main.py`](./main.py), se inician 2 procesos:

1. Se inicia el cliente, lo que incluye su GUI, el cliente del chat y un servidor asociado a la comunicación Cliente a cliente (mensaje privado).
2. De forma paralela (en un thread), se ejecuta el servidor, el cual tiene las siguientes particularidades:
    - Siempre se inicializa un servidor.
    - Todos menos el que fue inicializado con el flag `-s` se encuentran en espera de un mensaje para iniciar la migración (ver [migraciones](#migraciones)).
    - El que es inicializado con el flag `-s` actuará como el servidor inicial para el servicio de chat, y tendrá la logica para ejecutar la migración cuando se termine su tiempo (30 segundos según enunciado).

## DNS

Nuestro programa depende de un servidor DNS, el cual se encarga de mapear una URI a una IP en especifico.
En el momento de cambio de servidor, esta IP se cambia a la IP perteneciente al nuevo servidor, por lo que la conexión mediante la URI no cambia para los usuarios, es decir el proceso es transparente para ellos.

Esta arquitectura la podemos entender así:

![enter image description here](https://i.imgur.com/FIZ1vkv.png)

Dentro de cada maquina tendremos el cliente y un posible servidor para el programa (solo en el momento de cambio de servidor, los servidores inactivos pueden pasar a ser activos, como se puede ver en la siguiente sección (**Flujo y Migraciones**).

## Flujo y Migraciones

Para explicar el proceso de migración incorporado a la tarea 1 en la
presente tarea, explicamos el flujo a través de los siguientes pasos:

1. Se conecta el primer cliente: en esta máquina de cliente se corren en
primera instancia 2 procesos, el primero dice relación con un thread asociado
al **cliente** en sí y otro que representaría al proceso del **server latente**, como
este es el primer cliente en conectarse, dicho **servidor latente** pasaría a ser el
**server principal (activo)** de la aplicación (**decisión de diseño**) y una
vez establecido este server, se comunica con el **DNS Server** para actualizar su
su registro en la tabla de direcciones, `'backend.com' -> http://HOST:PORT`,
de manera que sea accesible por el resto de los clientes y procesos de servidor
latentes.
2. Una vez que transcurren los 30 segundos, el **servidor activo** (no latente) le solicita al DNS una address aleatoria de alguno de los servidores latentes. En este punto pueden ocurrir dos casos:
>
> - No se encuentra ningún servidor latente disponible en el **DNS**, en cuyo caso no se realiza ninguna migración y se omiten los siguientes pasos.
> - El **DNS** nos entrega un address valido, el cual apunta a uno de los servidores latentes. Luego se sigue con el paso **3**.
>
3. En este escenario el actual server activo, se comunica con el servidor latente
entregado, realizan un handshake y luego de eso comienza la transmisión de los
datos, del server activo antiguo al nuevo.
4. Una vez completado este proceso, el server activo antiguo se comunica con el
DNS Server para notificar el cambio de address, esto se hace efectivo en la
tabla de direcciones y este server activo antiguo, gatilla la reconexión de
todos los clientes al nuevo server activo.
5. Finalmente, se eliminan todos los mensajes del servidor antiguo con la finalidad de liberar memoria para los demás procesos.

**OBS. 1** Entre los puntos **3.** y **4.**, el cliente puede serguir enviando
mensajes pero estos se asignarán a una cola, que termina de enviarse una vez que
el nuevo server activo ya está 100% establecido.

**OBS. 2** La entrega es 100% funcional en una LAN.
