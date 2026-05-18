document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('assessment-form');
    const input = document.getElementById('patient-id');
    const submitBtn = form.querySelector('button[type="submit"]');
    const btnText = submitBtn.querySelector('.btn-text');
    const loader = submitBtn.querySelector('.loader');
    
    const resultSection = document.getElementById('result-section');
    const errorSection = document.getElementById('error-section');
    
    // Result elements
    const assessmentBadge = document.getElementById('assessment-badge');
    const reasoningText = document.getElementById('reasoning-text');
    const citationsList = document.getElementById('citations-list');
    const errorText = document.getElementById('error-text');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const patientId = input.value.trim();
        if (!patientId) return;

        // Reset UI State
        resultSection.classList.add('hidden');
        errorSection.classList.add('hidden');
        assessmentBadge.className = 'badge';
        assessmentBadge.textContent = '';
        reasoningText.textContent = '';
        citationsList.innerHTML = '';
        errorText.textContent = '';

        // Loading State
        submitBtn.disabled = true;
        btnText.classList.add('hidden');
        loader.classList.remove('hidden');

        try {
            const response = await fetch('/assess', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ patient_id: patientId })
            });

            const data = await response.json();

            if (!response.ok) {
                const errorMsg = data.detail && typeof data.detail === 'object'
                    ? (data.detail.message || data.detail.error || JSON.stringify(data.detail))
                    : (data.detail || data.error || 'Failed to process assessment.');
                throw new Error(errorMsg);
            }

            // Populate Results
            const assessmentLower = data.assessment.toLowerCase();
            if (assessmentLower.includes('urgent referral')) {
                assessmentBadge.classList.add('urgent');
            } else if (assessmentLower.includes('urgent investigation')) {
                assessmentBadge.classList.add('investigation');
            } else {
                assessmentBadge.classList.add('routine');
            }
            
            assessmentBadge.textContent = data.assessment;
            reasoningText.textContent = data.reasoning;
            
            if (data.citations && data.citations.length > 0) {
                data.citations.forEach(cit => {
                    const li = document.createElement('li');
                    li.textContent = cit;
                    citationsList.appendChild(li);
                });
            } else {
                const li = document.createElement('li');
                li.textContent = "No specific citations matched.";
                citationsList.appendChild(li);
            }

            // Show Results
            resultSection.classList.remove('hidden');

        } catch (error) {
            console.error('Error during assessment:', error);
            errorText.textContent = error.message;
            errorSection.classList.remove('hidden');
        } finally {
            // Restore button state
            submitBtn.disabled = false;
            btnText.classList.remove('hidden');
            loader.classList.add('hidden');
        }
    });
});
