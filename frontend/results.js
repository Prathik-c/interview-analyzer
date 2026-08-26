const sessionId = new URLSearchParams(window.location.search).get("session_id");
const resultsContent = document.getElementById("resultsContent");
const resultsMessage = document.getElementById("resultsMessage");

function textList(elementId, items) {
    document.getElementById(elementId).innerHTML = (items || []).map(function(item) {
        return `<li>${escapeHtml(item)}</li>`;
    }).join("");
}

function escapeHtml(value) {
    return String(value).replace(/[&<>\"]/g, function(character) {
        return { "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;" }[character];
    });
}

async function loadResults() {
    if (!sessionId) {
        resultsMessage.textContent = "This results link is missing its session ID.";
        resultsMessage.className = "connection-message error";
        return;
    }
    try {
        const response = await fetch(`/api/interview/session/${encodeURIComponent(sessionId)}`);
        const session = await response.json();
        if (!response.ok || !session.evaluation) {
            throw new Error(session.detail || "Results are not available yet.");
        }
        const evaluation = session.evaluation;
        document.getElementById("roleCopy").textContent = `${session.selected_role} interview results`;
        document.getElementById("scoreValue").textContent = evaluation.overall_score;
        document.getElementById("summary").textContent = evaluation.summary;
        textList("strengths", evaluation.strengths);
        textList("gaps", evaluation.gaps);
        document.getElementById("questionFeedback").innerHTML = (evaluation.per_question || []).map(function(item) {
            return `<article class="feedback-item"><div><strong>${escapeHtml(item.question)}</strong><span>${item.score}/10</span></div><p>${escapeHtml(item.feedback)}</p></article>`;
        }).join("");
        resultsContent.hidden = false;
    } catch (error) {
        resultsMessage.textContent = error.message;
        resultsMessage.className = "connection-message error";
    }
}

loadResults();