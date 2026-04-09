document.addEventListener("DOMContentLoaded", () => {
    cargarNavbar();
});

function cargarNavbar() {
    fetch("nav.html")
        .then(response => response.text())
        .then(data => {
            document.getElementById("navbar").innerHTML = data;
            establecerEnlaceActivo();
            activarMenuMovil();
        })
        .catch(error => console.error("Error al cargar el navbar:", error));
}

function establecerEnlaceActivo() {
    const links = document.querySelectorAll(".nav-links a");
    const paginaActual = window.location.pathname.split("/").pop() || "index.html";

    links.forEach(link => {
        if (link.getAttribute("href") === paginaActual) {
            link.classList.add("active");
        }
    });
}

function activarMenuMovil() {
    const toggle = document.getElementById("menu-toggle");
    const navLinks = document.getElementById("nav-links");

    if (toggle) {
        toggle.addEventListener("click", () => {
            navLinks.classList.toggle("show");
        });
    }
}

const toggle = document.getElementById("menu-toggle");
const navLinks = document.getElementById("nav-links");

if (toggle) {
    toggle.addEventListener("click", () => {
        navLinks.classList.toggle("show");
        toggle.classList.toggle("active");
    });
}