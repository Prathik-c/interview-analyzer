const sessionId = new URLSearchParams(window.location.search).get("session_id");
const questionsForm = document.getElementById("questionsForm");
const roleCopy = document.getElementById("roleCopy");
const progressLabel = document.getElementById("progressLabel");
const questionsMessage = document.getElementById("questionsMessage");
const finishButton = document.getElementById("finishButton");
let questionCount = 0;

function renderQuestions(session) {
    const answers = new Map((session.answers || []).map(function(item) {
        return [String(item.question_id), item.answer];
    }));

    roleCopy.textContent = `A focused ${session.selected_role} session, shaped around your experience.`;
    questionsForm.innerHTML = session.questions.map(function(item, index) {
        const answer = answers.get(String(item.id)) || "";
        return `<article class="question-card">
            <div class="question-meta"><span>Question ${index + 1}</span><span>${item.topic || item.source || "Interview"}</span></div>
            <h3>${escapeHtml(item.question)}</h3>
            <textarea id="answer-${item.id}" maxlength="5000" placeholder="Write your answer here...">${escapeHtml(answer)}</textarea>
            <button class="continue-button answer-button" type="button" data-question-id="${item.id}">
                Save answer <span aria-hidden="true">&#8594;</span>
            </button>
            <p class="answer-status" id="status-${item.id}" role="status"></p>
        </article>`;
    }).join("");

    updateProgress(answers);
    questionCount = session.questions.length;
    finishButton.disabled = answers.size < questionCount;
    questionsForm.querySelectorAll(".answer-button").forEach(function(button) {
        button.addEventListener("click", function() {
            saveAnswer(button, answers);
        });
    });
}

function escapeHtml(value) {
    return String(value).replace(/[&<>\"]/g, function(character) {
        return { "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;" }[character];
    });
}

function updateProgress(answers) {
    progressLabel.textContent = `${answers.size} answered`;
    finishButton.disabled = answers.size < questionCount;
}

async function saveAnswer(button, answers) {
    const questionId = Number(button.dataset.questionId);
    const textarea = document.getElementById(`answer-${questionId}`);
    const status = document.getElementById(`status-${questionId}`);
    const answer = textarea.value.trim();

    if (!answer) {
        status.textContent = "Add an answer before saving.";
        status.className = "answer-status error";
        return;
    }

    button.disabled = true;
    status.textContent = "Saving...";
    status.className = "answer-status";
    try {
        const response = await fetch("/api/interview/answer", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: sessionId, question_id: questionId, answer: answer })
        });
        const data = await response.json();
        if (!response.ok || !data.accepted) {
            throw new Error(data.detail || "Answer could not be saved.");
        }
        answers.set(String(questionId), answer);
        updateProgress(answers);
        status.textContent = "Answer saved.";
        status.className = "answer-status success";
    } catch (error) {
        status.textContent = error.message;
        status.className = "answer-status error";
    } finally {
        button.disabled = false;
    }
}

finishButton.addEventListener("click", async function() {
    finishButton.disabled = true;
    finishButton.classList.add("loading");
    questionsMessage.className = "connection-message";
    questionsMessage.textContent = "Reviewing your interview...";
    try {
        const response = await fetch(`/api/interview/evaluate?session_id=${encodeURIComponent(sessionId)}`, { method: "POST" });
        const data = await response.json();
        if (!response.ok || !data.accepted) {
            throw new Error(data.detail || "The interview could not be evaluated.");
        }
        window.location.href = `/results?session_id=${encodeURIComponent(sessionId)}`;
    } catch (error) {
        questionsMessage.textContent = error.message;
        questionsMessage.className = "connection-message error";
        finishButton.disabled = false;
    } finally {
        finishButton.classList.remove("loading");
    }
});

async function loadSession() {
    if (!sessionId) {
        questionsMessage.textContent = "This interview link is missing its session ID.";
        questionsMessage.className = "connection-message error";
        return;
    }

    try {
        const response = await fetch(`/api/interview/session/${encodeURIComponent(sessionId)}`);
        const session = await response.json();
        if (!response.ok) {
            throw new Error(session.detail || "Interview session not found.");
        }
        renderQuestions(session);
    } catch (error) {
        questionsMessage.textContent = error.message;
        questionsMessage.className = "connection-message error";
    }
}

loadSession();
