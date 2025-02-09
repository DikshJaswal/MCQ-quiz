document.getElementById('subject-form').addEventListener('submit', function(event) {
    event.preventDefault();
    const subject = document.getElementById('subject').value;

    // Store the selected subject
    localStorage.setItem('subject', subject);

    // Redirect to level selection page
    window.location.href = 'level-selection.html';
});
