document.getElementById('level-form').addEventListener('submit', function(event) {
    event.preventDefault();
    const level = document.getElementById('level').value;

    // Store the selected level
    localStorage.setItem('level', level);

    // Redirect to the AI-generated test page (or the question page)
    window.location.href = 'test.html'; // Or the page that will show the questions
});
