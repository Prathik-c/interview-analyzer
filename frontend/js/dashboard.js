document.addEventListener("DOMContentLoaded", async () => {
    // 1. Mandatory Auth Guard
    const user = await Auth.requireAuth("/login");
    if (!user) return;

    // 2. Initialize App Topbar
    await Auth.initAppNavbar("dashboard");

    // 3. Update Welcome Message with User's Name
    const welcomeHeading = document.getElementById("welcomeUserHeading");
    if (welcomeHeading && user.name) {
        welcomeHeading.textContent = `Welcome back, ${user.name} 👋`;
    }

    // 4. Fetch and render user history
    const loadingElem = document.getElementById("historyLoading");
    const containerElem = document.getElementById("historyContainer");
    const emptyElem = document.getElementById("historyEmpty");
    const avgScoreElem = document.getElementById("avgScoreVal");
    const countElem = document.getElementById("interviewCountVal");
    const bestScoreElem = document.getElementById("bestScoreVal");

    try {
        const sessions = await API.getUserHistory();
        loadingElem.style.display = "none";

        if (!sessions || sessions.length === 0) {
            emptyElem.style.display = "block";
            avgScoreElem.textContent = "—";
            countElem.textContent = "0";
            bestScoreElem.textContent = "—";
            return;
        }

        // Compute metrics
        let totalScore = 0;
        let evaluatedCount = 0;
        let bestScore = 0;

        sessions.forEach(s => {
            if (s.evaluation && typeof s.evaluation.overall_score === "number") {
                const sc = s.evaluation.overall_score;
                totalScore += sc;
                evaluatedCount++;
                if (sc > bestScore) bestScore = sc;
            }
        });

        countElem.textContent = sessions.length;
        if (evaluatedCount > 0) {
            const avg = Math.round(totalScore / evaluatedCount);
            avgScoreElem.textContent = `${avg}%`;
            bestScoreElem.textContent = `${bestScore}%`;
        } else {
            avgScoreElem.textContent = "—";
            bestScoreElem.textContent = "—";
        }

        // Render recent interview items
        containerElem.innerHTML = sessions.map(s => {
            const dateStr = s.created_at ? formatDate(s.created_at) : "Recent";
            const isCompleted = s.status === "completed" || Boolean(s.evaluation);
            const scoreVal = s.evaluation ? `${s.evaluation.overall_score}%` : (isCompleted ? "Completed" : "In Progress");

            let scoreClass = "history-score-badge";
            if (s.evaluation) {
                if (s.evaluation.overall_score >= 80) scoreClass += " high";
                else if (s.evaluation.overall_score >= 65) scoreClass += " mid";
                else scoreClass += " low";
            }

            const actionBtn = isCompleted
                ? `<a href="/results?session_id=${encodeURIComponent(s.session_id)}" class="btn btn-secondary" style="padding: 8px 16px; font-size: 13px;">View Report →</a>`
                : `<a href="/interview?session_id=${encodeURIComponent(s.session_id)}" class="btn btn-primary" style="padding: 8px 16px; font-size: 13px;">Resume Session →</a>`;

            return `
                <div class="history-card">
                    <div class="history-role-info">
                        <div class="history-role-name">${escapeHtml(s.selected_role || "Technical Interview")}</div>
                        <div class="history-role-meta">Taken on ${dateStr} • Session ID: ${escapeHtml(s.session_id.substring(0, 16))}...</div>
                    </div>

                    <div>
                        <span class="history-status-pill ${isCompleted ? 'completed' : 'active'}">
                            <span style="width: 6px; height: 6px; border-radius: 50%; background: currentColor;"></span>
                            ${isCompleted ? 'Evaluation Ready' : 'Active Interview'}
                        </span>
                    </div>

                    <div class="history-score-col">
                        <div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em;">Overall Score</div>
                        <div class="${scoreClass}">${scoreVal}</div>
                    </div>

                    <div>
                        ${actionBtn}
                    </div>
                </div>
            `;
        }).join("");

        containerElem.style.display = "flex";

    } catch (err) {
        console.error("Dashboard history load error:", err);
        loadingElem.style.display = "none";
        emptyElem.style.display = "block";
    }

    function formatDate(isoStr) {
        try {
            const d = new Date(isoStr);
            return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
        } catch {
            return "Recent";
        }
    }

    function escapeHtml(str) {
        return String(str || "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
    }
});
