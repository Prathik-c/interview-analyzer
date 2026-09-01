class CameraManager {
    constructor() {
        this.stream = null;
        this.mediaRecorder = null;
        this.recordedChunks = [];
        this.isRecording = false;
        this.videoElement = null;
    }

    async startCamera(videoElement) {
        this.videoElement = videoElement;
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

    startRecording() {
        if (!this.stream) return false;
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
            this.mediaRecorder.start(1000); // collect 1s slices
            this.isRecording = true;
            return true;
        } catch (e) {
            console.error("MediaRecorder init failed:", e);
            return false;
        }
    }

    stopRecording() {
        return new Promise((resolve) => {
            if (!this.mediaRecorder || !this.isRecording) {
                resolve(null);
                return;
            }
            this.mediaRecorder.onstop = () => {
                this.isRecording = false;
                const blob = new Blob(this.recordedChunks, { type: this.mediaRecorder.mimeType || "video/webm" });
                this.recordedChunks = [];
                resolve(blob);
            };
            this.mediaRecorder.stop();
        });
    }

    stopCamera() {
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }
        if (this.videoElement) {
            this.videoElement.srcObject = null;
        }
    }
}

window.cameraManager = new CameraManager();
