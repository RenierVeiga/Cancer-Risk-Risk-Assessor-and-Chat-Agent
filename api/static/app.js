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
                data.citations.forEach((cit, index) => {
                    const li = document.createElement('li');
                    if (cit && typeof cit === 'object') {
                        li.className = 'citation-card';
                        li.innerHTML = `
                            <div class="citation-card-header">
                                <span class="citation-card-source">${cit.source || 'NG12 PDF'} [${index + 1}]</span>
                                <span class="citation-card-page">Page ${cit.page ?? 'N/A'}</span>
                            </div>
                            <div class="citation-card-excerpt">
                                <em>"${(cit.excerpt || '').trim()}"</em>
                                <div class="citation-card-chunk">Chunk ID: ${cit.chunk_id || 'N/A'}</div>
                            </div>
                        `;
                    } else {
                        li.className = 'citation-item';
                        li.textContent = cit;
                    }
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

    // =====================================================================
    // PART 2: CHAT ASSISTANT TABS & CONVERSATIONAL AJAX INTERACTION
    // =====================================================================

    const tabBtnAssessor = document.getElementById('tab-btn-assessor');
    const tabBtnChat = document.getElementById('tab-btn-chat');
    const tabContentAssessor = document.getElementById('tab-content-assessor');
    const tabContentChat = document.getElementById('tab-content-chat');

    // Tab buttons event listeners
    tabBtnAssessor.addEventListener('click', () => {
        tabBtnAssessor.classList.add('active');
        tabBtnChat.classList.remove('active');
        tabContentAssessor.classList.remove('hidden');
        tabContentChat.classList.add('hidden');
    });

    tabBtnChat.addEventListener('click', () => {
        tabBtnChat.classList.add('active');
        tabBtnAssessor.classList.remove('active');
        tabContentChat.classList.remove('hidden');
        tabContentAssessor.classList.add('hidden');
        renderActiveChatSession();
        
        // Auto focus chat input and scroll to bottom
        setTimeout(() => {
            document.getElementById('chat-input').focus();
            const chatLog = document.getElementById('chat-log');
            chatLog.scrollTop = chatLog.scrollHeight;
        }, 100);
    });

    // Chat interaction logic
    const chatForm = document.getElementById('chat-input-form');
    const chatInput = document.getElementById('chat-input');
    const chatLog = document.getElementById('chat-log');
    const chatSessionList = document.getElementById('chat-session-list');
    const newChatBtn = document.getElementById('new-chat-btn');

    const CHAT_STORAGE_KEYS = {
        sessions: 'ng12_chat_sessions',
        activeSessionId: 'ng12_chat_active_session',
    };

    const WELCOME_MESSAGE = 'Hello! I am your Clinical Assistant grounded in the official NICE NG12 Suspected Cancer Guidelines. Please enter a Patient ID (e.g. PT-101) to start a new clinical session.';

    let chatSessions = loadChatSessions();
    let activeSessionId = localStorage.getItem(CHAT_STORAGE_KEYS.activeSessionId);
    let activePatientId = null;

    if (!chatSessions.length) {
        const initialSession = createChatSession();
        activeSessionId = initialSession.id;
    } else if (!activeSessionId || !chatSessions.some(session => session.id === activeSessionId)) {
        activeSessionId = chatSessions[0].id;
    }

    activePatientId = getActiveSession()?.patientId || null;
    syncChatSessionSidebar();
    renderActiveChatSession();
    updateChatInputPlaceholder();

    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const messageText = chatInput.value.trim();
        if (!messageText) return;

        chatInput.value = '';

        if (!activePatientId) {
            const patientMatch = messageText.toUpperCase().match(/^(PT-\d+)$/);
            if (!patientMatch) {
                appendChatMessage('user', messageText, 'You');
                appendChatMessage('clinician', 'Please enter a valid Patient ID (e.g. **PT-101**) to start a clinical session.', 'Clinical Assistant');
                scrollChatToBottom();
                return;
            }
        }

        const session = getActiveSession() || createChatSession();
        activeSessionId = session.id;
        localStorage.setItem(CHAT_STORAGE_KEYS.activeSessionId, activeSessionId);

        const localHistory = loadSessionHistory(session.id);

        appendChatMessage('user', messageText, 'You');

        const typingIndicator = appendTypingIndicator();
        scrollChatToBottom();

        const payloadHistory = localHistory.map(turn => ({
            role: turn.role === 'clinician' ? 'model' : turn.role,
            content: turn.content,
        }));

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    session_id: session.id,
                    message: messageText,
                    history: payloadHistory,
                    top_k: 5,
                    patient_id: activePatientId
                })
            });

            typingIndicator.remove();

            const data = await response.json();
            if (!response.ok) {
                const errMsg = data.detail || 'An error occurred during conversational search.';
                throw new Error(errMsg);
            }

            appendChatMessage('clinician', data.answer, 'Clinical Assistant', data.citations);
            scrollChatToBottom();

            if (data.patient_id && !activePatientId) {
                activePatientId = data.patient_id;
                updateSessionPatientId(session.id, activePatientId);
                updateChatInputPlaceholder();
            }

            localHistory.push({ role: 'user', content: messageText });
            localHistory.push({ role: 'clinician', content: data.answer, citations: data.citations });
            saveSessionHistory(session.id, localHistory);

            if (!session.title || session.title === 'New chat' || session.title.startsWith('Chat ')) {
                updateSessionTitle(session.id, deriveSessionTitle(session.id, localHistory));
            }

            syncChatSessionSidebar();

        } catch (error) {
            console.error('Chat error:', error);
            typingIndicator.remove();
            appendChatMessage('clinician', `Error: ${error.message}. Please verify the backend is running and Gemini credentials are authenticated.`, 'System Alert');
            scrollChatToBottom();
        }
    });

    chatSessionList.addEventListener('click', (event) => {
        const deleteButton = event.target.closest('[data-delete-session-id]');
        if (deleteButton) {
            const sessionId = deleteButton.dataset.deleteSessionId;
            deleteChatSession(sessionId);
            return;
        }

        const item = event.target.closest('[data-session-id]');
        if (!item) return;

        setActiveSession(item.dataset.sessionId);
    });

    chatSessionList.addEventListener('keydown', (event) => {
        if (event.key !== 'Enter' && event.key !== ' ') return;

        const focusedItem = event.target.closest('[data-session-id]');
        if (!focusedItem || event.target.closest('[data-delete-session-id]')) return;

        event.preventDefault();
        setActiveSession(focusedItem.dataset.sessionId);
    });

    newChatBtn.addEventListener('click', () => {
        startNewChatSession();
    });

    function loadChatSessions() {
        const raw = localStorage.getItem(CHAT_STORAGE_KEYS.sessions);
        if (!raw) return [];

        try {
            const parsed = JSON.parse(raw);
            return Array.isArray(parsed) ? parsed : [];
        } catch (err) {
            console.error('Error loading chat sessions:', err);
            return [];
        }
    }

    function persistChatSessions() {
        localStorage.setItem(CHAT_STORAGE_KEYS.sessions, JSON.stringify(chatSessions));
    }

    function createChatSession() {
        const session = {
            id: `session_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
            title: 'New chat',
            patientId: null,
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
        };

        chatSessions.unshift(session);
        persistChatSessions();
        localStorage.setItem(CHAT_STORAGE_KEYS.activeSessionId, session.id);
        return session;
    }

    function getActiveSession() {
        return chatSessions.find(session => session.id === activeSessionId) || null;
    }

    function getSessionHistoryKey(sessionId) {
        return `ng12_chat_history_${sessionId}`;
    }

    function loadSessionHistory(sessionId) {
        const raw = localStorage.getItem(getSessionHistoryKey(sessionId));
        if (!raw) return [];

        try {
            const parsed = JSON.parse(raw);
            return Array.isArray(parsed) ? parsed : [];
        } catch (err) {
            console.error(`Error loading chat history for ${sessionId}:`, err);
            return [];
        }
    }

    function saveSessionHistory(sessionId, history) {
        localStorage.setItem(getSessionHistoryKey(sessionId), JSON.stringify(history));
        touchSession(sessionId);
    }

    function touchSession(sessionId) {
        const session = chatSessions.find(item => item.id === sessionId);
        if (!session) return;

        session.updatedAt = new Date().toISOString();
        persistChatSessions();
    }

    function updateSessionTitle(sessionId, title) {
        const session = chatSessions.find(item => item.id === sessionId);
        if (!session) return;

        session.title = title || 'New chat';
        touchSession(sessionId);
        syncChatSessionSidebar();
    }

    function updateSessionPatientId(sessionId, patientId) {
        const session = chatSessions.find(item => item.id === sessionId);
        if (!session) return;

        session.patientId = patientId;
        if (session.title === 'New chat' || session.title.startsWith('Chat ')) {
            session.title = `Patient ${patientId}`;
        }
        touchSession(sessionId);
        syncChatSessionSidebar();
    }

    function deriveSessionTitle(sessionId, history) {
        const session = chatSessions.find(item => item.id === sessionId);
        if (session?.patientId) {
            return `Patient ${session.patientId}`;
        }

        const firstUserTurn = history.find(turn => turn.role === 'user');
        if (firstUserTurn?.content) {
            const normalized = firstUserTurn.content.trim().replace(/\s+/g, ' ');
            return normalized.length > 28 ? `${normalized.slice(0, 27)}…` : normalized;
        }

        return 'New chat';
    }

    function syncChatSessionSidebar() {
        if (!chatSessionList) return;

        const selectedId = activeSessionId;
        const sortedSessions = [...chatSessions].sort((a, b) => new Date(b.updatedAt) - new Date(a.updatedAt));

        chatSessionList.innerHTML = '';

        if (!sortedSessions.length) {
            const empty = document.createElement('div');
            empty.className = 'chat-session-empty';
            empty.textContent = 'No conversations yet. Start a new chat to create one.';
            chatSessionList.appendChild(empty);
            return;
        }

        sortedSessions.forEach(session => {
            const item = document.createElement('div');
            item.setAttribute('role', 'button');
            item.tabIndex = 0;
            item.className = `chat-session-item ${session.id === selectedId ? 'active' : ''}`;
            item.dataset.sessionId = session.id;

            const title = document.createElement('div');
            title.className = 'chat-session-item-title';
            title.textContent = buildSessionLabel(session);

            const meta = document.createElement('div');
            meta.className = 'chat-session-item-meta';

            const patient = document.createElement('span');
            patient.textContent = session.patientId ? session.patientId : 'General chat';

            const time = document.createElement('span');
            const updated = new Date(session.updatedAt);
            time.textContent = Number.isNaN(updated.getTime()) ? '' : updated.toLocaleDateString();

            meta.appendChild(patient);
            meta.appendChild(time);

            const actions = document.createElement('div');
            actions.className = 'chat-session-actions';

            const deleteButton = document.createElement('button');
            deleteButton.type = 'button';
            deleteButton.className = 'chat-session-delete-btn';
            deleteButton.dataset.deleteSessionId = session.id;
            deleteButton.setAttribute('aria-label', `Delete conversation ${buildSessionLabel(session)}`);
            deleteButton.textContent = 'Delete';

            actions.appendChild(deleteButton);

            item.appendChild(title);
            item.appendChild(meta);
            item.appendChild(actions);
            chatSessionList.appendChild(item);
        });

        chatSessionList.disabled = false;
    }

    function buildSessionLabel(session) {
        if (session.patientId) {
            return `${session.title || `Patient ${session.patientId}`} · ${session.patientId}`;
        }

        return session.title || 'New chat';
    }

    function setActiveSession(sessionId) {
        if (sessionId === activeSessionId) {
            renderActiveChatSession();
            return;
        }

        const targetSession = chatSessions.find(session => session.id === sessionId);
        if (!targetSession) return;

        activeSessionId = sessionId;
        activePatientId = targetSession.patientId || null;
        localStorage.setItem(CHAT_STORAGE_KEYS.activeSessionId, activeSessionId);
        updateChatInputPlaceholder();
        renderActiveChatSession();
        syncChatSessionSidebar();
    }

    function startNewChatSession() {
        const session = createChatSession();
        activeSessionId = session.id;
        activePatientId = null;
        localStorage.setItem(CHAT_STORAGE_KEYS.activeSessionId, activeSessionId);
        updateChatInputPlaceholder();
        renderActiveChatSession(true);
        syncChatSessionSidebar();
        chatInput.focus();
    }

    async function deleteChatSession(sessionId) {
        const session = chatSessions.find(item => item.id === sessionId);
        if (!session) return;

        const confirmDelete = window.confirm(`Delete conversation \"${buildSessionLabel(session)}\"? This cannot be undone.`);
        if (!confirmDelete) return;

        const wasActive = activeSessionId === sessionId;

        try {
            await fetch(`/chat/${encodeURIComponent(sessionId)}`, { method: 'DELETE' });
        } catch (err) {
            console.warn('Backend delete request failed, continuing with local deletion:', err);
        }

        localStorage.removeItem(getSessionHistoryKey(sessionId));
        chatSessions = chatSessions.filter(item => item.id !== sessionId);
        persistChatSessions();

        if (!chatSessions.length) {
            const session = createChatSession();
            activeSessionId = session.id;
            activePatientId = null;
            localStorage.setItem(CHAT_STORAGE_KEYS.activeSessionId, activeSessionId);
            renderActiveChatSession(true);
        } else if (wasActive) {
            const nextSession = chatSessions[0];
            activeSessionId = nextSession.id;
            activePatientId = nextSession.patientId || null;
            localStorage.setItem(CHAT_STORAGE_KEYS.activeSessionId, activeSessionId);
            renderActiveChatSession();
        }

        updateChatInputPlaceholder();
        syncChatSessionSidebar();
    }

    function updateChatInputPlaceholder() {
        chatInput.placeholder = activePatientId
            ? `Ask about Patient ${activePatientId} or NICE Guidelines...`
            : 'Enter Patient ID to begin (e.g. PT-101)...';
    }

    function renderWelcomeMessage() {
        appendChatMessage('clinician', WELCOME_MESSAGE, 'Clinical Assistant');
    }

    // Helper to load and render chat history from localStorage
    function loadChatHistory() {
        renderActiveChatSession();
    }

    function renderActiveChatSession(forceBlank = false) {
        const session = getActiveSession();
        chatLog.innerHTML = '';

        if (!session) {
            renderWelcomeMessage();
            scrollChatToBottom();
            return;
        }

        const history = forceBlank ? [] : loadSessionHistory(session.id);

        if (!history.length) {
            renderWelcomeMessage();
        } else {
            history.forEach(turn => {
                const sender = turn.role === 'user' ? 'user' : 'clinician';
                const name = turn.role === 'user' ? 'You' : 'Clinical Assistant';
                appendChatMessage(sender, turn.content, name, turn.citations || []);
            });
        }

        scrollChatToBottom();
    }

    // Helper to scroll chat log container to the bottom
    function scrollChatToBottom() {
        chatLog.scrollTop = chatLog.scrollHeight;
    }

    // Helper to append message bubbles to chat log
    function appendChatMessage(sender, text, name, citations = []) {
        const messageContainer = document.createElement('div');
        messageContainer.className = `chat-message ${sender}`;
        
        const bubble = document.createElement('div');
        bubble.className = 'chat-message-bubble';
        
        // Support custom basic markdown or bold tags if response returns them
        let formattedText = text
            .replace(/\n/g, '<br>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
            
        bubble.innerHTML = formattedText;
        
        // If there are citations, render them neatly below the bubble
        if (citations && citations.length > 0) {
            const citationsContainer = document.createElement('div');
            citationsContainer.className = 'chat-citations';
            
            const listTitle = document.createElement('div');
            listTitle.style.fontSize = '0.75rem';
            listTitle.style.fontWeight = '700';
            listTitle.style.color = 'var(--text-secondary)';
            listTitle.style.marginBottom = '0.25rem';
            listTitle.textContent = "VERIFIED GUIDELINE SOURCES:";
            citationsContainer.appendChild(listTitle);

            citations.forEach((cit, index) => {
                const citationCard = document.createElement('div');
                citationCard.className = 'chat-citation-item';
                
                citationCard.innerHTML = `
                    <div class="chat-citation-header">
                        <span class="chat-citation-source">NICE Guideline Reference [${index + 1}]</span>
                        <span class="chat-citation-page">Page ${cit.page}</span>
                    </div>
                    <div class="chat-citation-excerpt">
                        <em>"${(cit.excerpt || '').trim()}"</em>
                        <div style="font-size:0.7rem; color:var(--accent-blue); margin-top:0.4rem; text-transform:uppercase; font-weight:700;">Chunk ID: ${cit.chunk_id || 'N/A'}</div>
                    </div>
                `;
                
                // Add click-to-expand transition interaction
                citationCard.addEventListener('click', () => {
                    citationCard.classList.toggle('expanded');
                });
                
                citationsContainer.appendChild(citationCard);
            });
            
            bubble.appendChild(citationsContainer);
        }

        const meta = document.createElement('div');
        meta.className = 'chat-message-meta';
        meta.textContent = name;
        
        messageContainer.appendChild(bubble);
        messageContainer.appendChild(meta);
        chatLog.appendChild(messageContainer);
        return messageContainer;
    }

    // Helper to append loading dots typing indicator
    function appendTypingIndicator() {
        const indicator = document.createElement('div');
        indicator.className = 'chat-message clinician typing-indicator';
        
        const bubble = document.createElement('div');
        bubble.className = 'chat-message-bubble';
        bubble.style.padding = '0.6rem 1rem';
        
        const dots = document.createElement('div');
        dots.className = 'typing-dots';
        dots.innerHTML = '<span></span><span></span><span></span>';
        
        bubble.appendChild(dots);
        
        const meta = document.createElement('div');
        meta.className = 'chat-message-meta';
        meta.textContent = 'Clinical Assistant is reading guidelines...';
        
        indicator.appendChild(bubble);
        indicator.appendChild(meta);
        chatLog.appendChild(indicator);
        return indicator;
    }
});

