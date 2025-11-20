// Obtener datos del usuario desde localStorage
const usuario = JSON.parse(localStorage.getItem('usuario') || '{}');

// Función para enviar mensaje
async function enviarMensaje(tipo, mensaje) {
    const response = await fetch('/api/mensajes/enviar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            usuario: usuario.correo || 'invitado',
            tipo: tipo,
            mensaje: mensaje
        })
    });
    const data = await response.json();
    console.log(data);
}

// Función para recibir mensajes del admin
async function recibirMensajes() {
    const response = await fetch(`/api/mensajes/recibir?usuario=${usuario.correo}`);
    const mensajes = await response.json();
    const contenedor = document.getElementById('mensajes');
    contenedor.innerHTML = '';
    mensajes.forEach(m => {
        const div = document.createElement('div');
        div.classList.add('mensaje-admin');
        div.innerHTML = `<strong>${m.tipo}</strong>: ${m.mensaje}`;
        contenedor.appendChild(div);
    });
}

// Llamada periódica para actualizar mensajes cada 5 segundos
setInterval(recibirMensajes, 5000);

// Ejemplo de enviar mensaje desde un botón
document.getElementById('btnEnviar').addEventListener('click', () => {
    const tipo = document.getElementById('tipo').value;
    const mensaje = document.getElementById('mensaje').value;
    enviarMensaje(tipo, mensaje);
});
