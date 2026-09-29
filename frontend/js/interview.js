let timerInterval = null;
let timerSeconds = 0;

document.addEventListener("DOMContentLoaded", async () => {
    const videoElem = document.getElementById("webcamVideo");
    const questionCard = document.getElementById("questionCard");
    const recBadge = document.getElementById("recordingBadge");
    const timerElem = document.getElementById("recordingTimer");
    const startBtn = document.getElementById("startRecordBtn");
    const stopBtn = document.getElementById("stopRecordBtn");
    const finishBtn = document.getElementById("finishInterviewBtn");
    const textAnswerInput = document.getElementById("textAnswerInput");
    const saveTextBtn = document.getElementById("saveTextBtn");
    const transcriptBox = document.getElementById("transcriptBox");
    const statusMessage = document.getElementById("statusMessage");

    if (!window.state.sessionId) {
        if (statusMessage) statusMessage.textContent = "Session ID missing from URL. Please upload resume first.";
        return;
    }

    // 1. Load Session Data
    try {
        const session = await API.getSession(window.state.sessionId);
        window.state.setSession(session);
        renderCurrentQuestion();
    } catch (err) {
        if (statusMessage) statusMessage.textContent = err.message;
        return;
    }

    // 2. Start Camera Preview
    if (videoElem) {
        await window.cameraManager.startCamera(videoElem);
    }

    function renderCurrentQuestion() {
        const q = window.state.getCurrentQuestion();
        if (!q) return;

        const topicElem = document.getElementById("questionTopic");
        if (topicElem) {
            topicElem.textContent = `${q.topic || "Technical"} • Difficulty: ${q.difficulty || "MEDIUM"}`;
        }
        
        const numberElem = document.getElementById("questionNumber");
        if (numberElem) {
            numberElem.textContent = `Question ${window.state.currentQuestionIndex + 1} (Adaptive Stage)`;
        }

        const textElem = document.getElementById("questionText");
        if (textElem) {
            textElem.textContent = q.question;
        }

        const fillElem = document.getElementById("progressBarFill");
        if (fillElem) {
            const progressPct = Math.min(100, ((window.state.currentQuestionIndex + 1) / 5) * 100);
            fillElem.style.width = `${progressPct}%`;
        }

        // Check if question was already answered
        const existingAns = window.state.answers.get(q.id);
        if (existingAns) {
            if (textAnswerInput) textAnswerInput.value = existingAns.answer || "";
            if (transcriptBox) {
                transcriptBox.textContent = existingAns.answer ? `Processed Transcript: ${existingAns.answer}` : "";
                transcriptBox.hidden = !existingAns.answer;
            }
        } else {
            if (textAnswerInput) textAnswerInput.value = "";
            if (transcriptBox) transcriptBox.hidden = true;
        }

        updateFinishButton();
    }

    function updateFinishButton() {
        if (finishBtn) {
            const currentQ = window.state.getCurrentQuestion();
            const isLast = (window.state.currentQuestionIndex >= 4) || (currentQ && currentQ.id >= 5);
            if (isLast) {
                finishBtn.hidden = false;
                finishBtn.disabled = window.state.answers.size === 0;
            }
        }
    }

    async function showStageProgress() {
        const procCard = document.getElementById("processingCard");
        if (procCard) procCard.style.display = "block";

        const stepIds = ["procStep1", "procStep2", "procStep3", "procStep4", "procStep5", "procStep6"];
        stepIds.forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.className = "proc-step";
                const b = el.querySelector(".step-bullet");
                if (b) b.textContent = "○";
            }
        });

        for (let i = 0; i < stepIds.length; i++) {
            const el = document.getElementById(stepIds[i]);
            if (el) {
                el.className = "proc-step active";
                const b = el.querySelector(".step-bullet");
                if (b) b.textContent = "●";
            }
            if (i > 0) {
                const prev = document.getElementById(stepIds[i - 1]);
                if (prev) {
                    prev.className = "proc-step done";
                    const pb = prev.querySelector(".step-bullet");
                    if (pb) pb.textContent = "✓";
                }
            }
            await new Promise(r => setTimeout(r, 450));
        }

        const last = document.getElementById(stepIds[stepIds.length - 1]);
        if (last) {
            last.className = "proc-step done";
            const lb = last.querySelector(".step-bullet");
            if (lb) lb.textContent = "✓";
        }
        await new Promise(r => setTimeout(r, 300));
        if (procCard) procCard.style.display = "none";
    }

    // Start Recording Action
    if (startBtn) {
        startBtn.addEventListener("click", () => {
            const started = window.cameraManager.startRecording();
            if (started) {
                if (recBadge) recBadge.hidden = false;
                startBtn.hidden = true;
                if (stopBtn) stopBtn.hidden = false;
                timerSeconds = 0;
                if (timerElem) timerElem.textContent = "00:00";
                timerInterval = setInterval(() => {
                    timerSeconds++;
                    const mins = String(Math.floor(timerSeconds / 60)).padStart(2, '0');
                    const secs = String(timerSeconds % 60).padStart(2, '0');
                    if (timerElem) timerElem.textContent = `${mins}:${secs}`;
                }, 1000);
            }
        });
    }

    // Stop Recording & Upload Action with Stage Feedback & Adaptive Question Insertion
    if (stopBtn) {
        stopBtn.addEventListener("click", async () => {
            clearInterval(timerInterval);
            stopBtn.disabled = true;
            stopBtn.textContent = "Processing Multimodal Pipeline...";

            const blob = await window.cameraManager.stopRecording();
            if (recBadge) recBadge.hidden = true;
            startBtn.hidden = false;
            stopBtn.hidden = true;
            stopBtn.disabled = false;
            stopBtn.textContent = "Finish Answer & Submit";

            const currentQ = window.state.getCurrentQuestion();
            if (!currentQ) return;

            try {
                // Show processing stages
                const stagePromise = showStageProgress();
                const uploadPromise = API.uploadRecording(window.state.sessionId, currentQ.id, blob);
                
                const [_, res] = await Promise.all([stagePromise, uploadPromise]);

                window.state.answers.set(currentQ.id, {
                    question_id: currentQ.id,
                    answer: res.transcript
                });

                if (transcriptBox) {
                    transcriptBox.hidden = false;
                    transcriptBox.innerHTML = `<strong>Speech Transcript:</strong> ${res.transcript || "(No speech detected)"}<br><small style="color:var(--accent-cyan)">Technical NLP: ${res.nlp_score}/100 | WPM: ${res.speech_metrics?.words_per_minute || 0} | Fillers: ${res.speech_metrics?.filler_word_count || 0} | Posture: ${res.video_metrics?.posture_score || 85}%</small>`;
                }
                if (textAnswerInput) textAnswerInput.value = res.transcript || "";

                // If next question adaptively generated, append it to state and navigate
                if (res.next_question) {
                    const existingIdx = window.state.questions.findIndex(q => q.id === res.next_question.id);
                    if (existingIdx >= 0) {
                        window.state.questions[existingIdx] = res.next_question;
                    } else {
                        window.state.questions.push(res.next_question);
                    }

                    statusMessage.innerHTML = `<span style="color:var(--success)">✓ Answer analyzed! Next Adaptive Question generated: <strong>[${res.next_question.topic}]</strong></span>`;

                    // Advance to next adaptive question after 2 seconds
                    setTimeout(() => {
                        window.state.currentQuestionIndex = window.state.questions.length - 1;
                        renderCurrentQuestion();
                        if (statusMessage) statusMessage.textContent = "";
                    }, 2000);
                } else if (res.is_last_question) {
                    statusMessage.innerHTML = `<span style="color:var(--success)">✓ All interview questions completed! Click 'Complete & Finish Interview' for your final report.</span>`;
                    updateFinishButton();
                }

            } catch (err) {
                if (statusMessage) statusMessage.textContent = `Recording pipeline error: ${err.message}`;
            }
        });
    }

    // Manual Save Text Answer Action
    if (saveTextBtn) {
        saveTextBtn.addEventListener("click", async () => {
            const currentQ = window.state.getCurrentQuestion();
            const text = textAnswerInput ? textAnswerInput.value.trim() : "";
            if (!text) {
                if (window.UI) window.UI.showToast("Please enter an answer before saving.", "error");
                return;
            }
            try {
                saveTextBtn.disabled = true;
                const res = await API.saveTextAnswer(window.state.sessionId, currentQ.id, text);
                window.state.answers.set(currentQ.id, { question_id: currentQ.id, answer: text });
                if (window.UI) window.UI.showToast("Text answer saved!", "success");

                if (res.next_question) {
                    const existingIdx = window.state.questions.findIndex(q => q.id === res.next_question.id);
                    if (existingIdx >= 0) {
                        window.state.questions[existingIdx] = res.next_question;
                    } else {
                        window.state.questions.push(res.next_question);
                    }
                    setTimeout(() => {
                        window.state.currentQuestionIndex = window.state.questions.length - 1;
                        renderCurrentQuestion();
                    }, 1500);
                }
                updateFinishButton();
            } catch (err) {
                if (window.UI) window.UI.showToast(err.message, "error");
            } finally {
                saveTextBtn.disabled = false;
            }
        });
    }

    // Stepper Navigation
    document.getElementById("prevQuestionBtn")?.addEventListener("click", () => {
        if (window.state.currentQuestionIndex > 0) {
            window.state.currentQuestionIndex--;
            renderCurrentQuestion();
        }
    });

    document.getElementById("nextQuestionBtn")?.addEventListener("click", () => {
        if (window.state.currentQuestionIndex < window.state.questions.length - 1) {
            window.state.currentQuestionIndex++;
            renderCurrentQuestion();
        }
    });

    // Final Evaluate Action
    if (finishBtn) {
        finishBtn.addEventListener("click", async () => {
            finishBtn.disabled = true;
            finishBtn.textContent = "Generating Multimodal Evaluation...";
            if (statusMessage) {
                statusMessage.textContent = "Aggregating Groq NLP evaluations, Speech metrics, and MediaPipe posture records from PostgreSQL database...";
            }
            try {
                const res = await API.evaluateInterview(window.state.sessionId);
                if (window.cameraManager) window.cameraManager.stopCamera();
                window.location.href = `/results?session_id=${encodeURIComponent(window.state.sessionId)}`;
            } catch (err) {
                if (statusMessage) statusMessage.textContent = err.message;
                finishBtn.disabled = false;
                finishBtn.textContent = "Complete & Finish Interview →";
            }
        });
    }
});
