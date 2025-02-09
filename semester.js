document.getElementById('semester-form').addEventListener('submit', function(event) {
    event.preventDefault();
    const semester = document.getElementById('semester').value;
    
    // Store the selected semester (could be in localStorage/sessionStorage)
    localStorage.setItem('semester', semester);
    
    // Redirect to subject selection page
    window.location.href = 'subject-selection.html';
});
const backButton = document.getElementById('back-button');

if (backButton) {
    backButton.addEventListener('click', function() {
        // Go back to the previous page
        window.history.back();
    });
}