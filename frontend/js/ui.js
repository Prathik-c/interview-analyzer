const UI = {
    showToast(message, type = "info") {
        let toast = document.getElementById("uiToast");
        if (!toast) {
            toast = document.createElement("div");
            toast.id = "uiToast";
            toast.className = "toast";
            document.body.appendChild(toast);
        }
        toast.textContent = message;
        toast.style.borderColor = type === "error" ? "var(--status-red)" : (type === "success" ? "var(--status-green)" : "var(--accent-cyan)");
        toast.style.transform = "translateY(0)";

        setTimeout(() => {
            toast.style.transform = "translateY(100px)";
        }, 3500);
    },

    escapeHtml(value) {
        return String(value || "").replace(/[&<>"']/g, (char) => {
            return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char];
        });
    }
};

window.UI = UI;
