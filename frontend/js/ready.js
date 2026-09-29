document.addEventListener("DOMContentLoaded", async () => {
    // 1. Mandatory Auth Guard
    const user = await Auth.requireAuth("/login");
    if (!user) return;

    const urlParams = new URLSearchParams(window.location.search);
    const sessionId = urlParams.get("session_id");
    const role = urlParams.get("role") || "";

    if (!sessionId) {
        window.location.href = "/setup";
        return;
    }

    const sessionRoleBadge = document.getElementById("sessionRoleBadge");
    if (sessionRoleBadge && role) {
        sessionRoleBadge.textContent = `${role} • Readiness Check`;
    }

    const videoElem = document.getElementById("readyPreviewVideo");
    const videoOverlay = document.getElementById("videoOverlayBadge");
    const videoError = document.getElementById("videoErrorPlaceholder");
    const camStatusVal = document.getElementById("camStatusVal");
    const micStatusVal = document.getElementById("micStatusVal");
    const micDbLabel = document.getElementById("micDbLabel");
    const micMeterBar = document.getElementById("micMeterBar");
    const warningAlert = document.getElementById("cameraWarningAlert");
    const startBtn = document.getElementById("startInterviewBtn");
    const textModeBtn = document.getElementById("textModeBtn");

    let mediaStream = null;
    let audioCtx = null;
    let analyser = null;
    let animId = null;

    // 2. Initialize Camera and Microphone Test
    async function initDeviceTest() {
        try {
            mediaStream = await navigator.mediaDevices.getUserMedia({
                video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" },
                audio: true
            });

            if (videoElem) {
                videoElem.srcObject = mediaStream;
                await videoElem.play().catch(() => {});
                videoOverlay.style.display = "flex";
            }

            camStatusVal.textContent = "✓ Ready";
            camStatusVal.className = "dev-status-val";

            micStatusVal.textContent = "✓ Active";
            micStatusVal.className = "dev-status-val";

            setupMicVisualizer(mediaStream);

        } catch (err) {
            console.warn("Device access error in readiness check:", err);
            handleDeviceFailure();
        }
    }

    function setupMicVisualizer(stream) {
        try {
            const AudioContextClass = window.AudioContext || window.webkitAudioContext;
            audioCtx = new AudioContextClass();
            const source = audioCtx.createMediaStreamSource(stream);
            analyser = audioCtx.createAnalyser();
            analyser.fftSize = 256;
            source.connect(analyser);

            const bufferLength = analyser.frequencyBinCount;
            const dataArray = new Uint8Array(bufferLength);

            function updateMeter() {
                analyser.getByteFrequencyData(dataArray);
                let sum = 0;
                for (let i = 0; i < bufferLength; i++) {
                    sum += dataArray[i];
                }
                const average = sum / bufferLength;
                const volumePct = Math.min(100, Math.round((average / 128) * 100));

                if (micMeterBar) {
                    micMeterBar.style.width = `${volumePct}%`;
                }

                if (micDbLabel) {
                    if (volumePct > 5) {
                        micDbLabel.textContent = `Receiving Audio (${volumePct}%)`;
                        micDbLabel.style.color = "var(--status-green)";
                    } else {
                        micDbLabel.textContent = "Quiet Environment";
                        micDbLabel.style.color = "var(--text-muted)";
                    }
                }

                animId = requestAnimationFrame(updateMeter);
            }

            updateMeter();

        } catch (e) {
            console.warn("Audio meter setup error:", e);
            if (micDbLabel) micDbLabel.textContent = "Active";
        }
    }

    function handleDeviceFailure() {
        if (videoError) videoError.style.display = "block";
        if (camStatusVal) {
            camStatusVal.textContent = "Unavailable";
            camStatusVal.className = "dev-status-val error";
        }
        if (micStatusVal) {
            micStatusVal.textContent = "Unavailable";
            micStatusVal.className = "dev-status-val error";
        }
        if (warningAlert) warningAlert.style.display = "block";
        if (textModeBtn) textModeBtn.style.display = "block";
        if (micDbLabel) micDbLabel.textContent = "Disabled";
    }

    function cleanupDevices() {
        if (animId) cancelAnimationFrame(animId);
        if (audioCtx) {
            audioCtx.close().catch(() => {});
            audioCtx = null;
        }
        if (mediaStream) {
            mediaStream.getTracks().forEach(t => t.stop());
            mediaStream = null;
        }
        if (videoElem) {
            videoElem.srcObject = null;
        }
    }

    // 3. Navigation Actions
    startBtn.addEventListener("click", () => {
        cleanupDevices();
        window.location.href = `/interview?session_id=${encodeURIComponent(sessionId)}`;
    });

    if (textModeBtn) {
        textModeBtn.addEventListener("click", () => {
            cleanupDevices();
            window.location.href = `/interview?session_id=${encodeURIComponent(sessionId)}&mode=text`;
        });
    }

    // Clean up when leaving page
    window.addEventListener("beforeunload", cleanupDevices);

    // Run test
    initDeviceTest();
});
