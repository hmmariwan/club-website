const toggle = document.getElementById("menu-toggle");
const nav = document.getElementById("nav-links");

toggle.addEventListener("click", () => {
    nav.classList.toggle("active");
});

let slides = document.querySelectorAll(".slide");
let index = 0;

function showSlides() {
    slides.forEach((slide) => {
        slide.classList.remove("active");
    });

    index++;
    if (index >= slides.length) {
        index = 0;
    }

    slides[index].classList.add("active");
}

setInterval(showSlides, 5000); // 5 seconds

const accordions = document.querySelectorAll(".accordion-header");

accordions.forEach((btn) => {
    btn.addEventListener("click", () => {
        const content = btn.nextElementSibling;

        if (content.style.display === "block") {
            content.style.display = "none";
            btn.textContent = btn.textContent.replace("-", "+");
        } else {
            content.style.display = "block";
            btn.textContent = btn.textContent.replace("+", "-");
        }
    });
});

