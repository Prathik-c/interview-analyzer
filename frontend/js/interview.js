/**
 * interview.js — Continuous Recording Flow
 * Keeps camera/mic active across all questions.
 * Each "Next Question" stops current question clip, immediately starts
 * recording the next clip on the same stream, and uploads the previous clip.
 */

let timerInterval = null;
let timerSeconds = 0;
let isSubmitting = false;
let interviewEnded = false;
let pendingUpload = null; // Holds { blob, textAnswer, questionId, isLast } in case of retry

document.addEventListener("DOMContentLoaded", async () => {
    const videoElem        = document.getElementById("webcamVideo");
    const recBadge         = document.getElementById("recordingBadge");
    const timerElem        = document.getElementById("recordingTimer");
    const nextQuestionBtn  = document.getElementById("nextQuestionBtn");
    const textAnswerInput  = document.getElementById("textAnswerInput");
    const transcriptBox    = document.getElementById("transcriptBox");
    const statusMessage    = document.getElementById("statusMessage");
    const quitBtn          = document.getElementById("quitInterviewBtn");
    const quitModal        = document.getElementById("quitConfirmModal");
    const quitConfirmOk    = document.getElementById("quitConfirmOk");
    const quitConfirmClose = document.getElementById("quitConfirmClose");
    const completionBanner = document.getElementById("completionBanner");
    const questionText     = document.getElementById("questionText");
    const questionLoader   = document.getElementById("questionLoader");
    const uploadRetryBox   = document.getElementById("uploadRetryBox");
    const uploadRetryMsg   = document.getElementById("uploadRetryMsg");
    const retryUploadBtn   = document.getElementById("retryUploadBtn");

    // ── Auth guard ──────────────────────────────────────────────────────────
    if (window.Auth) {
        const user = await Auth.requireAuth("/login");
        if (!user) return;
    }

    if (!window.state || !window.state.sessionId) {
        if (statusMessage) statusMessage.textContent = "Session ID missing. Please upload resume first.";
        return;
    }

    // ── Load session ─────────────────────────────────────────────────────────
    try {
        const session = await API.getSession(window.state.sessionId);
        window.state.setSession(session);
        renderCurrentQuestion();
    } catch (err) {
        if (statusMessage) statusMessage.textContent = err.message || "Failed to load session.";
        return;
    }

    // ── Start camera preview & auto-start continuous recording ──────────────
    if (videoElem) {
        const camReady = await window.cameraManager.startCamera(videoElem);
        if (camReady) {
            startQuestionRecording();
        } else {
            if (statusMessage) {
                statusMessage.innerHTML = "<span style='color:var(--status-amber, #f59e0b)'>Camera unavailable. Text answers will be used for evaluation.</span>";
            }
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // UI Helpers
    // ─────────────────────────────────────────────────────────────────────────

    function renderCurrentQuestion() {
        const q = window.state.getCurrentQuestion();
        if (!q) return;

        const topicElem = document.getElementById("questionTopic");
        if (topicElem) topicElem.textContent = `${q.topic || "Technical"} • Difficulty: ${q.difficulty || "MEDIUM"}`;

        const numberElem = document.getElementById("questionNumber");
        if (numberElem) numberElem.textContent = `Question ${window.state.currentQuestionIndex + 1} of 5`;

        if (questionText) {
            questionText.textContent = q.question;
            questionText.style.display = "block";
        }
        if (questionLoader) {
            questionLoader.style.display = "none";
        }

        const fillElem = document.getElementById("progressBarFill");
        if (fillElem) {
            const pct = Math.min(100, ((window.state.currentQuestionIndex + 1) / 5) * 100);
            fillElem.style.width = `${pct}%`;
        }

        // Restore already-answered transcript if revisiting
        const existingAns = window.state.answers.get(q.id);
        if (existingAns) {
            if (textAnswerInput) textAnswerInput.value = existingAns.answer || "";
            if (transcriptBox) {
                transcriptBox.textContent = existingAns.answer ? `Transcript: ${existingAns.answer}` : "";
                transcriptBox.hidden = !existingAns.answer;
            }
        } else {
            if (textAnswerInput) textAnswerInput.value = "";
            if (transcriptBox) transcriptBox.hidden = true;
        }

        updateNextButtonLabel();
    }

    function updateNextButtonLabel() {
        if (!nextQuestionBtn) return;
        const isLast = (window.state.currentQuestionIndex >= 4);
        nextQuestionBtn.textContent = isLast ? "Finish Interview →" : "Next Question →";
    }

    function showQuestionLoading(loading) {
        if (questionLoader) questionLoader.style.display = loading ? "flex" : "none";
        if (questionText) questionText.style.display = loading ? "none" : "block";
    }

    function startTimer() {
        stopTimer();
        timerSeconds = 0;
        if (timerElem) timerElem.textContent = "00:00";
        timerInterval = setInterval(() => {
            timerSeconds++;
            const mins = String(Math.floor(timerSeconds / 60)).padStart(2, "0");
            const secs = String(timerSeconds % 60).padStart(2, "0");
            if (timerElem) timerElem.textContent = `${mins}:${secs}`;
        }, 1000);
    }

    function stopTimer() {
        if (timerInterval) {
            clearInterval(timerInterval);
            timerInterval = null;
        }
    }

    function startQuestionRecording() {
        if (interviewEnded) return;
        const started = window.cameraManager.startRecording();
        if (started) {
            if (recBadge) recBadge.hidden = false;
            startTimer();
            if (statusMessage) {
                statusMessage.innerHTML = `<span style="color:var(--accent-cyan)">● Recording Answer ${window.state.currentQuestionIndex + 1} of 5</span>`;
            }
        }
    }

    function showCompletionState() {
        interviewEnded = true;
        stopTimer();
        window.cameraManager.cleanup();

        if (recBadge) recBadge.hidden = true;
        if (nextQuestionBtn) {
            nextQuestionBtn.disabled = true;
            nextQuestionBtn.textContent = "Interview Completed";
        }
        if (quitBtn) quitBtn.style.display = "none";
        if (uploadRetryBox) uploadRetryBox.style.display = "none";

        if (completionBanner) {
            completionBanner.hidden = false;
            completionBanner.scrollIntoView({ behavior: "smooth" });
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Answer Submission & Next Flow
    // ─────────────────────────────────────────────────────────────────────────

    async function submitAnswerFlow(dataToUpload) {
        const { blob, textAnswer, questionId, isLast } = dataToUpload;

        if (uploadRetryBox) uploadRetryBox.style.display = "none";

        try {
            // Upload recording + optional text answer
            const res = await API.uploadRecording(window.state.sessionId, questionId, blob, textAnswer);

            // Record transcript / answer
            window.state.answers.set(questionId, {
                question_id: questionId,
                answer: res.transcript || textAnswer || ""
            });

            // Clear pending retry data on success
            pendingUpload = null;

            if (isLast) {
                showCompletionState();
                if (statusMessage) statusMessage.textContent = "Generating your multimodal evaluation report…";
                try {
                    await API.evaluateInterview(window.state.sessionId);
                } catch (e) {
                    console.warn("Evaluation completed with notice:", e);
                }
                setTimeout(() => {
                    window.location.href = `/results?session_id=${encodeURIComponent(window.state.sessionId)}`;
                }, 1800);
            } else {
                // Not last question: advance to next question
                if (res.next_question) {
                    const existingIdx = window.state.questions.findIndex(q => q.id === res.next_question.id);
                    if (existingIdx >= 0) {
                        window.state.questions[existingIdx] = res.next_question;
                    } else {
                        window.state.questions.push(res.next_question);
                    }
                    window.state.currentQuestionIndex = window.state.questions.length - 1;
                } else {
                    window.state.currentQuestionIndex = Math.min(window.state.questions.length - 1, window.state.currentQuestionIndex + 1);
                }

                showQuestionLoading(false);
                renderCurrentQuestion();

                // Start recording only when next question is displayed
                startQuestionRecording();

                if (nextQuestionBtn) {
                    nextQuestionBtn.disabled = false;
                    updateNextButtonLabel();
                }
            }
        } catch (err) {
            console.error("Submission failed:", err);
            // Save upload data so user can retry without losing their recording
            pendingUpload = dataToUpload;
            if (uploadRetryMsg) uploadRetryMsg.textContent = `Upload error: ${err.message || "Failed to submit recording."}`;
            if (uploadRetryBox) uploadRetryBox.style.display = "block";
            if (nextQuestionBtn) {
                nextQuestionBtn.disabled = false;
                nextQuestionBtn.textContent = "Retry Submitting Answer";
            }
            showQuestionLoading(false);
            if (questionText) questionText.style.display = "block";
        } finally {
            isSubmitting = false;
        }
    }

    if (nextQuestionBtn) {
        nextQuestionBtn.addEventListener("click", async () => {
            if (isSubmitting || interviewEnded) return;

            // If we have a pending failed upload, clicking here retries it
            if (pendingUpload) {
                isSubmitting = true;
                nextQuestionBtn.disabled = true;
                nextQuestionBtn.textContent = "Retrying upload…";
                await submitAnswerFlow(pendingUpload);
                return;
            }

            const currentQ = window.state.getCurrentQuestion();
            if (!currentQ) return;

            const isLast = (window.state.currentQuestionIndex >= 4) || (currentQ.id >= 5);
            const textAnswer = textAnswerInput ? textAnswerInput.value.trim() : "";

            isSubmitting = true;
            nextQuestionBtn.disabled = true;
            nextQuestionBtn.textContent = isLast ? "Finishing interview…" : "Preparing next question…";

            // 1. Stop current question's recorder to get its WebM Blob
            stopTimer();
            if (recBadge) recBadge.hidden = true;
            let blob = null;
            if (window.cameraManager && window.cameraManager.isRecording) {
                blob = await window.cameraManager.stopRecording();
            }

            const dataToUpload = {
                blob: blob,
                textAnswer: textAnswer,
                questionId: currentQ.id,
                isLast: isLast
            };

            // 2. While waiting for next question, show loader and keep live preview
            if (!isLast) {
                showQuestionLoading(true);
            }

            // 3. Upload current clip in parallel/background
            await submitAnswerFlow(dataToUpload);
        });
    }

    if (retryUploadBtn) {
        retryUploadBtn.addEventListener("click", async () => {
            if (pendingUpload && !isSubmitting) {
                isSubmitting = true;
                if (nextQuestionBtn) nextQuestionBtn.disabled = true;
                retryUploadBtn.disabled = true;
                retryUploadBtn.textContent = "Retrying…";
                await submitAnswerFlow(pendingUpload);
                retryUploadBtn.disabled = false;
                retryUploadBtn.textContent = "Retry Upload";
            }
        });
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Quit interview Modal
    // ─────────────────────────────────────────────────────────────────────────

    if (quitBtn && quitModal) {
        quitBtn.addEventListener("click", () => {
            quitModal.style.display = "flex";
        });
    }

    if (quitConfirmClose) {
        quitConfirmClose.addEventListener("click", () => {
            if (quitModal) quitModal.style.display = "none";
        });
    }

    if (quitConfirmOk) {
        quitConfirmOk.addEventListener("click", async () => {
            if (quitModal) quitModal.style.display = "none";
            interviewEnded = true;
            stopTimer();

            if (window.cameraManager && window.cameraManager.isRecording) {
                await window.cameraManager.stopRecording().catch(() => {});
            }
            if (window.cameraManager) {
                window.cameraManager.cleanup();
            }

            try {
                await API.abandonSession(window.state.sessionId);
            } catch (e) {
                console.warn("Could not mark session as abandoned:", e);
            }

            window.location.href = "/dashboard";
        });
    }

    if (quitModal) {
        quitModal.addEventListener("click", (e) => {
            if (e.target === quitModal) quitModal.style.display = "none";
        });
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Page Unload Cleanup
    // ─────────────────────────────────────────────────────────────────────────

    window.addEventListener("beforeunload", () => {
        stopTimer();
        if (window.cameraManager && !interviewEnded) {
            window.cameraManager.cleanup();
        }
    });
});
