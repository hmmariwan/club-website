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
