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
    const cancerBadge = document.getElementById('cancer-badge');
    const reasoningText = document.getElementById('reasoning-text');
    const matchedRulesList = document.getElementById('matched-rules-list');
    const nextStepsList = document.getElementById('next-steps-list');
    const citationsList = document.getElementById('citations-list');
    const errorText = document.getElementById('error-text');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const patientId = input.value.trim();
        if (!patientId) return;

        // Reset UI State
        resultSection.classList.add('hidden');
        errorSection.classList.add('hidden');
        
        // Clear badges
        assessmentBadge.className = 'badge';
        assessmentBadge.textContent = '';
        
        cancerBadge.className = 'badge cancer-badge hidden';
        cancerBadge.textContent = '';
        
        // Clear text and lists
        reasoningText.textContent = '';
        matchedRulesList.innerHTML = '';
        nextStepsList.innerHTML = '';
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

            // 1. Populate Assessment Status Badge
            const statusLower = data.assessment_status.toLowerCase();
            if (statusLower.includes('urgent referral')) {
                assessmentBadge.classList.add('urgent');
            } else if (statusLower.includes('urgent investigation')) {
                assessmentBadge.classList.add('investigation');
            } else {
                assessmentBadge.classList.add('routine');
            }
            assessmentBadge.textContent = data.assessment_status;

            // 2. Populate Primary Suspected Cancer Badge
            if (data.primary_suspected_cancer && data.primary_suspected_cancer !== 'None') {
                cancerBadge.classList.remove('hidden');
                cancerBadge.textContent = data.primary_suspected_cancer;
            }

            // 3. Populate Clinical Synthesis Reasoning
            reasoningText.textContent = data.clinical_reasoning;

            // 4. Render Matched NICE Recommendations Cards
            if (data.matched_rules && data.matched_rules.length > 0) {
                data.matched_rules.forEach(rule => {
                    const card = document.createElement('div');
                    card.className = 'matched-rule-card';
                    
                    // Header containing ID and Site
                    const header = document.createElement('div');
                    header.className = 'rule-card-header';
                    
                    const title = document.createElement('span');
                    title.className = 'rule-card-title';
                    title.innerHTML = `Recommendation <strong>${rule.recommendation_id}</strong> <span class="rule-site-divider">•</span> ${rule.cancer_site}`;
                    
                    const pathway = document.createElement('span');
                    pathway.className = `rule-pathway-badge ${rule.pathway.toLowerCase().includes('referral') ? 'pathway-referral' : 'pathway-investigation'}`;
                    pathway.textContent = rule.pathway;
                    
                    header.appendChild(title);
                    header.appendChild(pathway);
                    
                    // Body text of the guideline criteria
                    const body = document.createElement('p');
                    body.className = 'rule-card-body';
                    body.textContent = rule.guideline_text;
                    
                    // Footer list of matched patient symptoms as badges
                    const footer = document.createElement('div');
                    footer.className = 'rule-card-footer';
                    
                    const symptomLabel = document.createElement('span');
                    symptomLabel.className = 'symptom-label';
                    symptomLabel.textContent = "Matched Symptoms: ";
                    footer.appendChild(symptomLabel);
                    
                    rule.matched_symptoms.forEach(symptom => {
                        const pill = document.createElement('span');
                        pill.className = 'symptom-pill';
                        pill.textContent = symptom;
                        footer.appendChild(pill);
                    });
                    
                    card.appendChild(header);
                    card.appendChild(body);
                    card.appendChild(footer);
                    matchedRulesList.appendChild(card);
                });
            } else {
                const noRules = document.createElement('div');
                noRules.className = 'no-rules-alert';
                noRules.textContent = "No specific NICE guideline thresholds or high-risk rules were triggered.";
                matchedRulesList.appendChild(noRules);
            }

            // 5. Render GP Actionable Next Steps as Checkboxes
            let steps = [];
            if (data.recommended_next_steps.includes('\n')) {
                steps = data.recommended_next_steps.split('\n')
                    .map(line => line.replace(/^[\s\-\*\d\.\:\)]+/, '').trim())
                    .filter(line => line.length > 0);
            } else {
                steps = [data.recommended_next_steps];
            }

            steps.forEach((step, idx) => {
                const li = document.createElement('li');
                li.className = 'next-step-item';
                
                const label = document.createElement('label');
                label.className = 'checkbox-container';
                
                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.id = `step-${idx}`;
                
                const checkmark = document.createElement('span');
                checkmark.className = 'checkmark';
                
                const text = document.createElement('span');
                text.className = 'step-text';
                text.textContent = step;
                
                label.appendChild(checkbox);
                label.appendChild(checkmark);
                label.appendChild(text);
                li.appendChild(label);
                nextStepsList.appendChild(li);
            });

            // 6. Populate Citations List
            if (data.citations && data.citations.length > 0) {
                data.citations.forEach(cit => {
                    const li = document.createElement('li');
                    li.className = 'citation-item';
                    li.textContent = cit;
                    citationsList.appendChild(li);
                });
            } else {
                const li = document.createElement('li');
                li.className = 'citation-item';
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
