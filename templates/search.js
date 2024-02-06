document.addEventListener('DOMContentLoaded', function () {
    const searchInput = document.getElementById('searchInput');
    const surveyContainer = document.getElementById('surveyContainer');
    const allSurveys = JSON.parse('{{ surveys | tojson | safe }}');

    searchInput.addEventListener('input', function () {
        const searchTerm = searchInput.value.toLowerCase();

        // Filter surveys based on substring match
        const filteredSurveys = allSurveys.filter(survey => survey.name.toLowerCase().includes(searchTerm));

        // Clear existing survey items
        surveyContainer.innerHTML = '';

        // Render updated survey items
        filteredSurveys.forEach(survey => {
            const surveyItem = `
                <!-- Survey item HTML here with updated data -->
            `;
            surveyContainer.innerHTML += surveyItem;
        });
    });
}); 