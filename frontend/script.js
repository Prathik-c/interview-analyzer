const jobRoles = [
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

const defaultRoles = [
    "Software Engineer",
    "Machine Learning Engineer",
    "Data Scientist",
    "Frontend Developer",
    "Data Analyst"
];

const input = document.getElementById("jobTitleInput");
const results = document.getElementById("jobResults");
const emptyState = document.getElementById("emptyState");
const continueButton = document.getElementById("continueButton");
const selectionHint = document.getElementById("selectionHint");
const connectionMessage = document.getElementById("connectionMessage");
const API_URL = "/api/interview/start";

let selectedRole = null;

function displayRoles(roles) {
    results.innerHTML = "";
    emptyState.hidden = roles.length > 0;

    roles.forEach(function(role) {
        const button = document.createElement("button");

        button.textContent = role;
        button.classList.add("job-option");

        if (role === selectedRole) {
            button.classList.add("selected");
        }

        button.addEventListener("click", function() {
            selectedRole = role;

            document.querySelectorAll(".job-option").forEach(function(option) {
                option.classList.remove("selected");
            });

            button.classList.add("selected");
            continueButton.disabled = false;
            selectionHint.textContent = `${selectedRole} selected`;
            connectionMessage.textContent = "";

            console.log("Selected role:", selectedRole);
        });

        results.appendChild(button);
    });
}

displayRoles(defaultRoles);

input.addEventListener("input", function() {
    const searchText = input.value.toLowerCase().trim();

    if (searchText === "") {
        displayRoles(defaultRoles);
        return;
    }

    const filteredRoles = jobRoles.filter(function(role) {
        return role.toLowerCase().includes(searchText);
    });

    displayRoles(filteredRoles);
});

continueButton.addEventListener("click", async function() {
    if (!selectedRole) {
        return;
    }

    continueButton.disabled = true;
    continueButton.classList.add("loading");
    connectionMessage.className = "connection-message";
    connectionMessage.textContent = "Connecting to your interview session...";

    try {
        const response = await fetch(API_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ selected_role: selectedRole })
        });

        if (!response.ok) {
            throw new Error("The interview session could not be started.");
        }

        const data = await response.json();
        connectionMessage.classList.add("success");
        connectionMessage.textContent = `Ready for your ${data.selected_role} interview.`;
        window.location.href = `/resume?role=${encodeURIComponent(data.selected_role)}`;
    } catch (error) {
        connectionMessage.classList.add("error");
        connectionMessage.textContent = "Could not connect. Make sure the backend is running on port 8000.";
        continueButton.disabled = false;
    } finally {
        continueButton.classList.remove("loading");
    }
});