const resumeForm = document.getElementById("resumeForm");
const resumeFile = document.getElementById("resumeFile");
const uploadZone = document.getElementById("uploadZone");
const uploadTitle = document.getElementById("uploadTitle");
const uploadButton = document.getElementById("uploadButton");
const resumeMessage = document.getElementById("resumeMessage");

function showSelectedFile() {
    const file = resumeFile.files[0];
    if (!file) {
        uploadTitle.textContent = "Drop your resume here";
        uploadButton.disabled = true;
        return;
    }

    uploadTitle.textContent = file.name;
    uploadButton.disabled = false;
    uploadZone.classList.add("has-file");
    resumeMessage.textContent = "";
}

resumeFile.addEventListener("change", showSelectedFile);

["dragenter", "dragover"].forEach(function(eventName) {
    uploadZone.addEventListener(eventName, function(event) {
        event.preventDefault();
        uploadZone.classList.add("dragging");
    });
});

["dragleave", "drop"].forEach(function(eventName) {
    uploadZone.addEventListener(eventName, function(event) {
        event.preventDefault();
        uploadZone.classList.remove("dragging");
    });
});

uploadZone.addEventListener("drop", function(event) {
    resumeFile.files = event.dataTransfer.files;
    showSelectedFile();
});

resumeForm.addEventListener("submit", async function(event) {
    event.preventDefault();
    const file = resumeFile.files[0];
    if (!file) {
        return;
    }

    uploadButton.disabled = true;
    uploadButton.classList.add("loading");
    resumeMessage.className = "connection-message";
    resumeMessage.textContent = "Uploading your resume...";

    try {
        const formData = new FormData();
        formData.append("file", file);
        const response = await fetch("/api/interview/resume", { method: "POST", body: formData });
        const data = await response.json();

        if (!response.ok || !data.accepted) {
            throw new Error(data.message || "Resume upload failed.");
        }

        resumeMessage.classList.add("success");
        resumeMessage.textContent = `${data.filename} is ready for your interview.`;
    } catch (error) {
        resumeMessage.classList.add("error");
        resumeMessage.textContent = error.message;
        uploadButton.disabled = false;
    } finally {
        uploadButton.classList.remove("loading");
    }
});
