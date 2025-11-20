// ======================
// Variables
// ======================
let productos = [];
let productosFiltrados = [];
let paginaActual = 0;
const productosPorPagina = 12;

const contenedor = document.getElementById("productos-container");
const carritoIcon = document.getElementById("carrito-icon");
const carritoVentana = document.getElementById("carrito-ventana");
const carritoItemsDiv = document.getElementById("carrito-items");
const carritoCount = document.getElementById("carrito-count");
const carritoTotalDiv = document.getElementById("carrito-total");
const cerrarCarritoBtn = document.getElementById("cerrar-carrito");
const busquedaInput = document.getElementById("busqueda");
const btnBuscar = document.getElementById("btn-buscar");

let carrito = [];

// ======================
// Funciones
// ======================

// Cargar productos desde FastAPI
async function cargarProductos() {
    try {
        const res = await fetch("/producto");
        if (!res.ok) throw new Error("No hay productos disponibles");
        productos = await res.json();
        productosFiltrados = [...productos];
        paginaActual = 0;
        mostrarPagina();
    } catch (err) {
        contenedor.innerHTML = "<p style='text-align:center; font-weight:bold;'>No hay productos para mostrar</p>";
        console.warn(err.message);
    }
}

// Mostrar productos en la página
function mostrarPagina() {
    contenedor.innerHTML = "";
    if (!productosFiltrados || productosFiltrados.length === 0) {
        contenedor.innerHTML = "<p style='text-align:center; font-weight:bold;'>No se encontraron productos</p>";
        return;
    }

    const inicio = paginaActual * productosPorPagina;
    const fin = Math.min(inicio + productosPorPagina, productosFiltrados.length);
    const lista = productosFiltrados.slice(inicio, fin);

    lista.forEach(p => {
        const card = document.createElement("div");
        card.className = "producto-card";
        card.innerHTML = `
            <div><b>Código:</b> ${p.Codigo}</div>
            <div><b>Nombre:</b> ${p.Nombre}</div>
            <div><b>Precio:</b> $${p.Precio.toFixed(2)}</div>
            <div><b>Existencia:</b> ${p.Existencia}</div>
            <button class="btn-agregar">Agregar al carrito</button>
        `;
        contenedor.appendChild(card);

        // Evento seguro
        card.querySelector(".btn-agregar").addEventListener("click", () => {
            agregarAlCarrito(p.Codigo);
        });
    });
}

// ======================
// Carrito
// ======================
function agregarAlCarrito(codigo) {
    const producto = productos.find(p => p.Codigo === codigo);
    if (!producto) return;

    const existente = carrito.find(p => p.Codigo === codigo);
    if (existente) {
        existente.cantidad++;
    } else {
        carrito.push({ ...producto, cantidad: 1 });
    }

    actualizarCarrito();
    abrirCarrito();
}

function eliminarDelCarrito(codigo) {
    carrito = carrito.filter(p => p.Codigo !== codigo);
    actualizarCarrito();
}

function cambiarCantidad(codigo, cantidad) {
    const producto = carrito.find(p => p.Codigo === codigo);
    if (!producto) return;
    producto.cantidad = Math.max(1, cantidad);
    actualizarCarrito();
}

function actualizarCarrito() {
    carritoItemsDiv.innerHTML = "";
    let total = 0;

    if (carrito.length === 0) {
        carritoItemsDiv.innerHTML = "<p>El carrito está vacío</p>";
    }

    carrito.forEach(p => {
        const itemDiv = document.createElement("div");
        itemDiv.className = "carrito-item";
        itemDiv.innerHTML = `
            <span>${p.Nombre}</span>
            <input type="number" min="1" value="${p.cantidad}" class="cantidad-input" />
            <span>$${(p.Precio * p.cantidad).toFixed(2)}</span>
            <button class="eliminar-btn">X</button>
        `;
        carritoItemsDiv.appendChild(itemDiv);

        // Eliminar producto
        itemDiv.querySelector(".eliminar-btn").addEventListener("click", () => eliminarDelCarrito(p.Codigo));

        // Cambiar cantidad
        itemDiv.querySelector(".cantidad-input").addEventListener("change", e => {
            let nuevaCantidad = parseInt(e.target.value) || 1;
            cambiarCantidad(p.Codigo, nuevaCantidad);
        });

        total += p.Precio * p.cantidad;
    });

    carritoTotalDiv.textContent = `Total: $${total.toFixed(2)}`;
    carritoCount.textContent = carrito.reduce((acc, p) => acc + p.cantidad, 0);
}

function abrirCarrito() {
    carritoVentana.style.display = "block";
}

function cerrarCarrito() {
    carritoVentana.style.display = "none";
}

// ======================
// Eventos
// ======================
carritoIcon.addEventListener("click", () => {
    carritoVentana.style.display = carritoVentana.style.display === "none" ? "block" : "none";
});
cerrarCarritoBtn.addEventListener("click", cerrarCarrito);

// Paginación
document.getElementById("inicio").addEventListener("click", () => { paginaActual = 0; mostrarPagina(); });
document.getElementById("atras").addEventListener("click", () => { if (paginaActual > 0) paginaActual--; mostrarPagina(); });
document.getElementById("siguiente").addEventListener("click", () => { if ((paginaActual + 1) * productosPorPagina < productosFiltrados.length) paginaActual++; mostrarPagina(); });

// Búsqueda
function filtrarProductos() {
    const filtro = busquedaInput.value.toLowerCase();
    productosFiltrados = productos.filter(p =>
        (p.Codigo || "").toLowerCase().includes(filtro) ||
        (p.Nombre || "").toLowerCase().includes(filtro)
    );
    paginaActual = 0;
    mostrarPagina();
}

btnBuscar.addEventListener("click", filtrarProductos);
busquedaInput.addEventListener("keypress", e => {
    if (e.key === "Enter") filtrarProductos();
});

// ======================
// Inicializar
// ======================
cargarProductos();
