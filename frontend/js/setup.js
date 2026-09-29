document.addEventListener("DOMContentLoaded", async () => {
    // 1. Mandatory Auth Guard
    const user = await Auth.requireAuth("/login");
    if (!user) return;

    // 2. Initialize App Topbar
    await Auth.initAppNavbar("setup");

    // Elements
    const dropZone = document.getElementById("setupDropZone");
    const fileInput = document.getElementById("resumeFileInput");
    const uploadZoneTitle = document.getElementById("uploadZoneTitle");
    const previewContainer = document.getElementById("parsedResumePreview");
    const previewFileName = document.getElementById("previewFileName");
    const previewCandidateName = document.getElementById("previewCandidateName");
    const roleSelect = document.getElementById("roleSelect");
    const quickRolesContainer = document.getElementById("quickRolesContainer");
    const continueBtn = document.getElementById("continueBtn");
    const alertBox = document.getElementById("setupAlert");

    let selectedFile = null;
    let selectedRole = "";

    // 30 Supported Roles Fallback matching backend constants
    const ALL_ROLES = [
        "Software Engineer",
        "Frontend Developer",
        "Backend Developer",
        "Full Stack Developer",
        "Mobile App Developer",
        "Java Developer",
        "Python Developer",
        "C++ Developer",
        "Machine Learning Engineer",
        "Machine Learning Researcher",
        "AI Engineer",
        "Deep Learning Engineer",
        "Computer Vision Engineer",
        "NLP Engineer",
        "Generative AI Engineer",
        "MLOps Engineer",
        "Data Scientist",
        "Data Analyst",
        "Data Engineer",
        "Business Intelligence Analyst",
        "DevOps Engineer",
        "Cloud Engineer",
        "Cloud Architect",
        "Cybersecurity Engineer",
        "Product Manager",
        "Project Manager",
        "UI/UX Designer",
        "QA Engineer",
        "Test Engineer"
    ];

    const POPULAR_ROLES = [
        "Machine Learning Engineer",
        "Software Engineer",
        "Data Scientist",
        "Frontend Developer",
        "Backend Developer",
        "DevOps Engineer"
    ];

    // 3. Load Roles into Select Dropdown and Quick Chips
    async function loadRoles() {
        let roles = ALL_ROLES;
        try {
            const apiRoles = await API.getJobRoles();
            if (apiRoles && apiRoles.length > 0) {
                roles = apiRoles;
            }
        } catch (e) {
            console.warn("Could not fetch remote roles, using defaults:", e);
        }

        // Populate Dropdown
        roles.forEach(r => {
            const opt = document.createElement("option");
            opt.value = r;
            opt.textContent = r;
            roleSelect.appendChild(opt);
        });

        // Populate Quick Chips
        quickRolesContainer.innerHTML = "";
        POPULAR_ROLES.forEach(r => {
            const chip = document.createElement("button");
            chip.type = "button";
            chip.className = "quick-role-chip";
            chip.textContent = r;
            chip.onclick = () => {
                selectRole(r);
            };
            quickRolesContainer.appendChild(chip);
        });
    }

    function selectRole(role) {
        selectedRole = role;
        roleSelect.value = role;

        // Update active chip state
        document.querySelectorAll(".quick-role-chip").forEach(chip => {
            if (chip.textContent === role) {
                chip.classList.add("selected");
            } else {
                chip.classList.remove("selected");
            }
        });

        validateForm();
    }

    roleSelect.addEventListener("change", () => {
        selectRole(roleSelect.value);
    });

    // 4. File Drag & Drop & Upload Handling
    function handleFile(file) {
        if (!file) return;

        if (!file.name.toLowerCase().endsWith(".pdf")) {
            showAlert("Please upload a valid PDF file (.pdf).", "error");
            return;
        }

        if (file.size > 10 * 1024 * 1024) {
            showAlert("File size exceeds 10MB limit. Please upload a smaller PDF.", "error");
            return;
        }

        selectedFile = file;
        hideAlert();

        // Update visual zone
        dropZone.classList.add("has-file");
        uploadZoneTitle.textContent = `Attached: ${file.name}`;

        // Update preview card
        previewFileName.textContent = `${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
        previewCandidateName.textContent = user.name ? `${user.name} — Resume Ready` : "Resume Attached";
        previewContainer.style.display = "block";

        validateForm();
    }

    fileInput.addEventListener("change", (e) => {
        if (e.target.files && e.target.files[0]) {
            handleFile(e.target.files[0]);
        }
    });

    ["dragover", "dragenter"].forEach(evt => {
        dropZone.addEventListener(evt, (e) => {
            e.preventDefault();
            dropZone.classList.add("dragging");
        });
    });

    ["dragleave", "drop"].forEach(evt => {
        dropZone.addEventListener(evt, (e) => {
            e.preventDefault();
            dropZone.classList.remove("dragging");
        });
    });

    dropZone.addEventListener("drop", (e) => {
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            handleFile(e.dataTransfer.files[0]);
        }
    });

    function validateForm() {
        const isValid = Boolean(selectedFile && selectedRole);
        continueBtn.disabled = !isValid;
    }

    function showAlert(msg, type) {
        alertBox.textContent = msg;
        alertBox.style.display = "block";
        if (type === "error") {
            alertBox.style.background = "rgba(239, 68, 68, 0.12)";
            alertBox.style.border = "1px solid rgba(239, 68, 68, 0.3)";
            alertBox.style.color = "#FCA5A5";
        } else {
            alertBox.style.background = "rgba(0, 242, 254, 0.1)";
            alertBox.style.border = "1px solid rgba(0, 242, 254, 0.25)";
            alertBox.style.color = "var(--accent-cyan)";
        }
    }

    function hideAlert() {
        alertBox.style.display = "none";
    }

    // 5. Submit Form / Upload & Create Session
    continueBtn.addEventListener("click", async () => {
        if (!selectedFile || !selectedRole) return;

        continueBtn.disabled = true;
        continueBtn.textContent = "Uploading & Extracting Resume with AI...";
        showAlert("Parsing PDF resume and generating tailored technical questions...", "info");

        try {
            const res = await API.uploadResume(selectedFile, selectedRole);
            continueBtn.textContent = "Session Created! Initializing Readiness Check...";
            showAlert("Resume parsed successfully! Directing to device readiness check...", "info");

            setTimeout(() => {
                window.location.href = `/interview-ready?session_id=${encodeURIComponent(res.session_id)}&role=${encodeURIComponent(selectedRole)}`;
            }, 600);

        } catch (err) {
            console.error("Resume upload error:", err);
            showAlert("Unable to process your resume. Please make sure the file is a valid PDF and try again.", "error");
            continueBtn.disabled = false;
            continueBtn.textContent = "Continue to Readiness Check →";
        }
    });

    // Initialize
    loadRoles();
});
