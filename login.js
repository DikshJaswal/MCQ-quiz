document.getElementById('login-form').addEventListener('submit', function(event) {
    event.preventDefault(); // Prevents the default form submission
    
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;

    if(username && password) {
        // Redirect to the next page after login (just a placeholder for now)
        window.location.href = 'semester-selection.html'; // or any other page
    } else {
        alert("Please fill out both fields");
    }
});
// Get the Sign Up button element
const signupButton = document.getElementById('signup-button');

// Add an event listener to the button
signupButton.addEventListener('click', function() {
    // Redirect to the sign-up page (change 'signup.html' to your actual sign-up page)
    window.location.href = 'signup.html';
});