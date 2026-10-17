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

        if (evalData.evaluation_status === "evaluation_failed" || evalData.overall_score === null) {
            if (errorMsg) {
                errorMsg.innerHTML = `
                    <div style="background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.35); padding: 12px 18px; border-radius: 8px; display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 16px;">
                        <div>
                            <strong style="color: #fca5a5;">Evaluation Notice:</strong>
                            <span style="color: var(--text-secondary); margin-left: 6px;">Evaluation could not be fully completed by provider. Unmeasured signals are excluded and shown as "Not measured".</span>
                        </div>
                        <button type="button" class="btn btn-secondary" id="retryEvalBtn" style="font-size: 13px; padding: 6px 14px; color: #fca5a5; border-color: rgba(239, 68, 68, 0.5); white-space: nowrap;">
                            Retry Evaluation
                        </button>
                    </div>
                `;
                const retryBtn = document.getElementById("retryEvalBtn");
                if (retryBtn) {
                    retryBtn.onclick = async () => {
                        retryBtn.disabled = true;
                        retryBtn.textContent = "Re-evaluating…";
                        try {
                            await API.evaluateInterview(sessionId);
                            window.location.reload();
                        } catch (e) {
                            alert("Retry evaluation failed: " + (e.message || "Unknown error"));
                            retryBtn.disabled = false;
                            retryBtn.textContent = "Retry Evaluation";
                        }
                    };
                }
            }
        }

        renderDashboard(data.selected_role, evalData);
    } catch (err) {
        if (errorMsg) errorMsg.textContent = err.message;
    }

    function renderDashboard(role, evaluation) {
        document.getElementById("roleTitle").textContent = `${role} Performance Assessment`;
        document.getElementById("overallScoreVal").textContent = (evaluation.overall_score !== null && evaluation.overall_score !== undefined) ? evaluation.overall_score : "Not measured";
        document.getElementById("summaryText").textContent = evaluation.summary;

        // Metric breakdown values
        document.getElementById("nlpScoreVal").textContent = (evaluation.nlp_score !== null && evaluation.nlp_score !== undefined) ? `${evaluation.nlp_score}%` : "Not measured";
        document.getElementById("speechScoreVal").textContent = (evaluation.speech_score !== null && evaluation.speech_score !== undefined) ? `${evaluation.speech_score}%` : "Not measured";
        document.getElementById("videoScoreVal").textContent = (evaluation.video_score !== null && evaluation.video_score !== undefined) ? `${evaluation.video_score}%` : "Not measured";

        // Animate metric bars
        const nlpBar = document.getElementById("nlpBarFill");
        const speechBar = document.getElementById("speechBarFill");
        const videoBar = document.getElementById("videoBarFill");
        if (nlpBar) nlpBar.style.width = (evaluation.nlp_score !== null && evaluation.nlp_score !== undefined) ? `${evaluation.nlp_score}%` : "0%";
        if (speechBar) speechBar.style.width = (evaluation.speech_score !== null && evaluation.speech_score !== undefined) ? `${evaluation.speech_score}%` : "0%";
        if (videoBar) videoBar.style.width = (evaluation.video_score !== null && evaluation.video_score !== undefined) ? `${evaluation.video_score}%` : "0%";

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
        strengthsList.innerHTML = (evaluation.strengths || []).map(s => `<li><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block; vertical-align:-1px; margin-right:6px;"><polyline points="20 6 9 17 4 12"/></svg> ${UI.escapeHtml(s)}</li>`).join("");

        // Gaps / Improvements
        const gapsList = document.getElementById("gapsList");
        gapsList.innerHTML = (evaluation.gaps || []).map(g => `<li><span>•</span> ${UI.escapeHtml(g)}</li>`).join("");

        // Delivery & Speech aggregate insights
        const deliveryCard = document.getElementById("deliveryInsightsCard");
        if (deliveryCard && (evaluation.avg_wpm || evaluation.total_filler_count !== null || evaluation.total_pause_count !== null)) {
            deliveryCard.hidden = false;
            const wpmEl = document.getElementById("statAvgWpm");
            const fillEl = document.getElementById("statTotalFillers");
            const pauseEl = document.getElementById("statTotalPauses");
            if (wpmEl) wpmEl.textContent = evaluation.avg_wpm ? `${evaluation.avg_wpm} WPM` : "N/A";
            if (fillEl) {
                let fillText = evaluation.total_filler_count !== null && evaluation.total_filler_count !== undefined ? String(evaluation.total_filler_count) : "0";
                fillEl.textContent = fillText;
            }
            if (pauseEl) {
                let pauseText = evaluation.total_pause_count !== null && evaluation.total_pause_count !== undefined ? String(evaluation.total_pause_count) : "0";
                if (evaluation.total_long_pause_count) {
                    pauseText += ` (${evaluation.total_long_pause_count} long)`;
                }
                pauseEl.textContent = pauseText;
            }

            const notesContainer = document.getElementById("deliveryNotesContainer");
            if (notesContainer) {
                let notesHtml = "";
                if (evaluation.longest_pause_seconds) {
                    notesHtml += `
                        <div style="font-size: 13px; color: var(--text-secondary); display: flex; align-items: flex-start; gap: 8px;">
                            <span style="color: var(--accent-cyan); display:inline-flex; align-items:center;"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg></span>
                            <span>Longest pause detected: <strong>${evaluation.longest_pause_seconds}s</strong></span>
                        </div>
                    `;
                }
                if (evaluation.filler_breakdown && Object.keys(evaluation.filler_breakdown).length > 0) {
                    const breakdownChips = Object.entries(evaluation.filler_breakdown)
                        .map(([w, c]) => `<span style="background: rgba(255,255,255,0.06); padding: 2px 8px; border-radius: 4px; margin-right: 6px; font-size: 12px; color: #FCD34D;">"${UI.escapeHtml(w)}": ${c}</span>`)
                        .join("");
                    notesHtml += `
                        <div style="font-size: 13px; color: var(--text-secondary); display: flex; align-items: flex-start; gap: 8px; margin-top: 4px;">
                            <span style="color: #FCD34D; display:inline-flex; align-items:center;"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg></span>
                            <span>Filler breakdown: ${breakdownChips}</span>
                        </div>
                    `;
                }
                if (evaluation.delivery_pattern_notes && evaluation.delivery_pattern_notes.length > 0) {
                    notesHtml += evaluation.delivery_pattern_notes.map(n => `
                        <div style="font-size: 13px; color: var(--text-secondary); display: flex; align-items: flex-start; gap: 8px;">
                            <span style="color: var(--accent-cyan); display:inline-flex; align-items:center;"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg></span>
                            <span>${UI.escapeHtml(n)}</span>
                        </div>
                    `).join("");
                }
                notesContainer.innerHTML = notesHtml;
            }
        }

        // Question Breakdown Cards with concept coverage & rich signals
        const qContainer = document.getElementById("questionBreakdownList");
        qContainer.innerHTML = (evaluation.per_question || []).map((q, idx) => {
            const hasCovered = Array.isArray(q.covered_concepts) && q.covered_concepts.length > 0;
            const hasMissing = Array.isArray(q.missing_concepts) && q.missing_concepts.length > 0;
            const hasMisconceptions = Array.isArray(q.misconceptions) && q.misconceptions.length > 0;

            const coveredHtml = hasCovered ? `
                <div class="concept-tag-group">
                    <span style="font-size: 11px; font-weight: 700; color: #6EE7B7; margin-right: 4px; display: flex; align-items: center;">Covered:</span>
                    ${q.covered_concepts.map(c => `<span class="concept-chip covered">${UI.escapeHtml(c)}</span>`).join("")}
                </div>
            ` : '';

            const missingHtml = hasMissing ? `
                <div class="concept-tag-group">
                    <span style="font-size: 11px; font-weight: 700; color: #FCD34D; margin-right: 4px; display: flex; align-items: center;">Missing:</span>
                    ${q.missing_concepts.map(c => `<span class="concept-chip missing">Missing: ${UI.escapeHtml(c)}</span>`).join("")}
                </div>
            ` : '';

            const misconceptionsHtml = hasMisconceptions ? `
                <div class="misconception-alert">
                    <strong>Technical Misconceptions:</strong>
                    <ul style="margin: 4px 0 0 18px; padding: 0;">
                        ${q.misconceptions.map(m => `<li>${UI.escapeHtml(m)}</li>`).join("")}
                    </ul>
                </div>
            ` : '';

            const reasoningHtml = q.reasoning_summary ? `
                <div class="reasoning-summary-card">
                    <strong>Analysis:</strong> ${UI.escapeHtml(q.reasoning_summary)}
                </div>
            ` : '';

            const methodHtml = q.evaluation_method ? `
                <span class="method-tag">${UI.escapeHtml(q.evaluation_method)}</span>
            ` : '';

            const modalitiesHtml = (q.modalities_used && q.modalities_used.length > 0) ? `
                <span class="method-tag" style="background: rgba(99,179,237,0.15); color: var(--accent-cyan);">Signals: ${q.modalities_used.join(", ")}</span>
            ` : '';

            const scoreText = (q.score !== null && q.score !== undefined) ? `Score: ${q.score}/100` : "Score: Not measured";
            const nlpText = (q.nlp_score !== null && q.nlp_score !== undefined) ? `${q.nlp_score}%` : "Not measured";
            const speechText = (q.speech_score !== null && q.speech_score !== undefined) ? `${q.speech_score}%` : "Not measured";
            const videoText = (q.video_score !== null && q.video_score !== undefined) ? `${q.video_score}%` : "Not measured";

            let speechDetailHtml = '';
            if (q.pause_count !== null && q.pause_count !== undefined) {
                const pauseStr = `${q.pause_count} pause${q.pause_count === 1 ? '' : 's'}` +
                    (q.long_pause_count ? ` (${q.long_pause_count} > 2s)` : '') +
                    (q.longest_pause_seconds ? `, longest ${q.longest_pause_seconds}s` : '');
                const fillerTypes = q.filler_breakdown && Object.keys(q.filler_breakdown).length > 0
                    ? ` (${Object.entries(q.filler_breakdown).map(([k, v]) => `${k}: ${v}`).join(', ')})`
                    : '';
                const fillerStr = `${q.filler_word_count || 0} filler${(q.filler_word_count === 1) ? '' : 's'}${fillerTypes}`;
                speechDetailHtml = `
                    <div style="font-size: 12px; color: var(--text-muted); margin-top: 6px; display: flex; gap: 16px; flex-wrap: wrap;">
                        <span>Pauses: <strong>${pauseStr}</strong></span>
                        <span>Fillers: <strong>${fillerStr}</strong></span>
                    </div>
                `;
            }

            return `
                <div class="question-result-card">
                    <div class="q-res-header">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <strong>Question ${idx + 1}</strong>
                            ${methodHtml}
                            ${modalitiesHtml}
                        </div>
                        <span class="q-res-score">${scoreText}</span>
                    </div>
                    <h4 style="font-family:var(--font-heading); margin-bottom: 8px;">${UI.escapeHtml(q.question)}</h4>
                    <p style="color:var(--text-secondary); font-size:14px; margin-bottom:12px;">${UI.escapeHtml(q.feedback)}</p>
                    
                    ${q.transcript ? `<div class="transcript-box"><strong>Transcript:</strong> "${UI.escapeHtml(q.transcript)}"</div>` : ''}
                    ${speechDetailHtml}
                    ${coveredHtml}
                    ${missingHtml}
                    ${misconceptionsHtml}
                    ${reasoningHtml}

                    <div style="display:flex; gap:16px; margin-top:12px; font-size:12px; color:var(--accent-cyan); flex-wrap: wrap;">
                        <span>NLP Quality: ${nlpText}</span>
                        <span>Speech Score: ${speechText}</span>
                        <span>Video Score: ${videoText}</span>
                    </div>
                </div>
            `;
        }).join("");

        // Setup PDF download triggers
        setupPdfDownload(sessionId);

        container.hidden = false;
    }

    function setupPdfDownload(sid) {
        const triggers = document.querySelectorAll(".download-pdf-trigger");
        triggers.forEach(btn => {
            btn.onclick = async () => {
                const originalHtml = btn.innerHTML;
                try {
                    btn.disabled = true;
                    btn.innerHTML = `Generating PDF...`;

                    const response = await API.downloadReport(sid);
                    const blob = await response.blob();
                    const downloadUrl = window.URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = downloadUrl;
                    a.download = `interview_report_${sid.slice(0, 8)}.pdf`;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    window.URL.revokeObjectURL(downloadUrl);

                    btn.innerHTML = `Downloaded!`;
                    setTimeout(() => {
                        btn.innerHTML = originalHtml;
                        btn.disabled = false;
                    }, 2500);
                } catch (err) {
                    console.error("PDF download failed:", err);
                    alert("Failed to download PDF report: " + (err.message || "Unknown error"));
                    btn.innerHTML = originalHtml;
                    btn.disabled = false;
                }
            };
        });
    }
});
