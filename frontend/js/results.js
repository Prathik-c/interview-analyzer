document.addEventListener("DOMContentLoaded", async () => {
    const sessionId = new URLSearchParams(window.location.search).get("session_id");
    const container = document.getElementById("resultsContainer");
    const errorMsg = document.getElementById("errorMessage");

    if (!sessionId) {
        if (errorMsg) errorMsg.textContent = "Session ID missing from URL.";
        return;
    }

    try {
        const data = await API.getSession(sessionId);
        const evalData = data.evaluation;
        if (!evalData) {
            throw new Error("Evaluation results not ready for this session.");
        }

        renderDashboard(data.selected_role, evalData);
    } catch (err) {
        if (errorMsg) errorMsg.textContent = err.message;
    }

    function renderDashboard(role, evaluation) {
        document.getElementById("roleTitle").textContent = `${role} Performance Assessment`;
        document.getElementById("overallScoreVal").textContent = evaluation.overall_score;
        document.getElementById("summaryText").textContent = evaluation.summary;

        // Metric breakdown values
        document.getElementById("nlpScoreVal").textContent = `${evaluation.nlp_score}%`;
        document.getElementById("speechScoreVal").textContent = `${evaluation.speech_score}%`;
        document.getElementById("videoScoreVal").textContent = `${evaluation.video_score}%`;

        // Animate metric bars
        const nlpBar = document.getElementById("nlpBarFill");
        const speechBar = document.getElementById("speechBarFill");
        const videoBar = document.getElementById("videoBarFill");
        if (nlpBar) nlpBar.style.width = `${evaluation.nlp_score}%`;
        if (speechBar) speechBar.style.width = `${evaluation.speech_score}%`;
        if (videoBar) videoBar.style.width = `${evaluation.video_score}%`;

        // Wire logout button
        const logoutBtn = document.getElementById("appLogoutBtn");
        if (logoutBtn) {
            logoutBtn.onclick = () => {
                if (window.Auth) Auth.logout();
                else {
                    localStorage.removeItem("auth_token");
                    window.location.href = "/login";
                }
            };
        }

        // Strengths
        const strengthsList = document.getElementById("strengthsList");
        strengthsList.innerHTML = (evaluation.strengths || []).map(s => `<li><span>✓</span> ${UI.escapeHtml(s)}</li>`).join("");

        // Gaps / Improvements
        const gapsList = document.getElementById("gapsList");
        gapsList.innerHTML = (evaluation.gaps || []).map(g => `<li><span>•</span> ${UI.escapeHtml(g)}</li>`).join("");

        // Question Breakdown Cards
        const qContainer = document.getElementById("questionBreakdownList");
        qContainer.innerHTML = (evaluation.per_question || []).map((q, idx) => `
            <div class="question-result-card">
                <div class="q-res-header">
                    <strong>Question ${idx + 1}</strong>
                    <span class="q-res-score">Score: ${q.score}/100</span>
                </div>
                <h4 style="font-family:var(--font-heading); margin-bottom: 8px;">${UI.escapeHtml(q.question)}</h4>
                <p style="color:var(--text-secondary); font-size:14px; margin-bottom:12px;">${UI.escapeHtml(q.feedback)}</p>
                ${q.transcript ? `<div class="transcript-box"><strong>Transcript:</strong> "${UI.escapeHtml(q.transcript)}"</div>` : ''}
                <div style="display:flex; gap:16px; margin-top:12px; font-size:12px; color:var(--accent-cyan);">
                    <span>NLP Quality: ${q.nlp_score ?? q.score}%</span>
                    <span>Speech Score: ${q.speech_score ?? 'N/A'}%</span>
                    <span>Video Score: ${q.video_score ?? 'N/A'}%</span>
                </div>
            </div>
        `).join("");

        container.hidden = false;
    }
});
