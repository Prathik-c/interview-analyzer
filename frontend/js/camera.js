class CameraManager {
    constructor() {
        this.stream = null;
        this.mediaRecorder = null;
        this.recordedChunks = [];
        this.isRecording = false;
        this.videoElement = null;
        this._resolveStop = null;
    }

    async startCamera(videoElement) {
        this.videoElement = videoElement;
        // Keep single stream open throughout whole interview
        if (this.stream && this.stream.active) {
            if (this.videoElement && this.videoElement.srcObject !== this.stream) {
                this.videoElement.srcObject = this.stream;
                await this.videoElement.play().catch(() => {});
            }
            return true;
        }

        try {
            this.stream = await navigator.mediaDevices.getUserMedia({
                video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" },
                audio: true
            });
            if (this.videoElement) {
                this.videoElement.srcObject = this.stream;
                await this.videoElement.play().catch(() => {});
            }
            return true;
        } catch (error) {
            console.error("Camera access denied or unavailable:", error);
            if (window.UI) UI.showToast("Camera/Microphone access required for live interview.", "error");
            return false;
        }
    }

    /**
     * Start a fresh MediaRecorder for the current question using the existing active stream.
     * Starts continuous recording (no timeslice chunks) so onstop generates a valid standalone WebM.
     */
    startRecording() {
        if (!this.stream || !this.stream.active) {
            console.warn("Cannot start recording: camera stream is not active.");
            return false;
        }

        // Clean up previous recorder if still running
        if (this.isRecording && this.mediaRecorder) {
            try { this.mediaRecorder.stop(); } catch (e) {}
            this.isRecording = false;
        }

        this.recordedChunks = [];
        const mimeType = MediaRecorder.isTypeSupported("video/webm;codecs=vp9,opus")
            ? "video/webm;codecs=vp9,opus"
            : (MediaRecorder.isTypeSupported("video/webm") ? "video/webm" : "video/mp4");

        try {
            this.mediaRecorder = new MediaRecorder(this.stream, { mimeType });
            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data && event.data.size > 0) {
                    this.recordedChunks.push(event.data);
                }
            };
            this.mediaRecorder.onstop = () => {
                this.isRecording = false;
                const blob = new Blob(this.recordedChunks, { type: this.mediaRecorder.mimeType || "video/webm" });
                this.recordedChunks = [];
                if (this._resolveStop) {
                    this._resolveStop(blob);
                    this._resolveStop = null;
                }
            };

            // Start continuous recording for this question clip
            this.mediaRecorder.start();
            this.isRecording = true;
            return true;
        } catch (e) {
            console.error("MediaRecorder init failed:", e);
            return false;
        }
    }

    /**
     * Stop the current question's MediaRecorder and return a Promise resolving to the recorded WebM Blob.
     */
    stopRecording() {
        return new Promise((resolve) => {
            if (!this.mediaRecorder || !this.isRecording) {
                resolve(null);
                return;
            }
            this._resolveStop = resolve;
            try {
                this.mediaRecorder.stop();
            } catch (e) {
                console.error("MediaRecorder stop error:", e);
                this.isRecording = false;
                this._resolveStop = null;
                resolve(null);
            }
        });
    }

    /** Stop the camera preview and release all media hardware tracks. */
    stopCamera() {
        if (this.isRecording && this.mediaRecorder) {
            try {
                this._resolveStop = () => {};
                this.mediaRecorder.stop();
            } catch (e) { /* ignore */ }
            this.isRecording = false;
        }
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }
        if (this.videoElement) {
            this.videoElement.srcObject = null;
        }
        this.mediaRecorder = null;
        this.recordedChunks = [];
    }

    /** Full cleanup — call on page unload or interview end. */
    cleanup() {
        this.stopCamera();
    }
}

window.cameraManager = new CameraManager();

// Release hardware tracks when user navigates away or closes tab
window.addEventListener("pagehide", () => {
    if (window.cameraManager) window.cameraManager.cleanup();
});
