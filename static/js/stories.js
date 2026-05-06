const accordions = document.querySelectorAll(".accordion-header"); 
accordions.forEach((btn) => { btn.addEventListener("click", () => { 
    const content = btn.nextElementSibling; 
    if (content.style.display === "block") { 
        content.style.display = "none"; 
        btn.textContent = btn.textContent.replace("-", "+"); } 
        else { content.style.display = "block"; 
            btn.textContent = btn.textContent.replace("+", "-"); } 
        }); 
    });