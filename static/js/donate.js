let selectedAmount = 0;

function selectAmount(amount, event) {
    selectedAmount = amount;
    document.getElementById("custom-amount").value = amount;

    // remove previous selection highlight
    document.querySelectorAll(".amount-options button").forEach(btn => {
        btn.classList.remove("selected");
    });

    // highlight clicked button
    event.target.classList.add("selected");
}

// form submit
document.getElementById("donation-form").addEventListener("submit", function(e) {
    e.preventDefault();

    const amount = document.getElementById("custom-amount").value;

    if (!amount || amount <= 0) {
        alert("Please enter a valid donation amount.");
        return;
    }

    // fake payment delay
    setTimeout(() => {
        document.getElementById("success-message").style.display = "block";
        document.getElementById("donation-form").reset();

        // reset selected state
        document.querySelectorAll(".amount-options button").forEach(btn => {
            btn.classList.remove("selected");
        });

        selectedAmount = 0;

    }, 800);
});

