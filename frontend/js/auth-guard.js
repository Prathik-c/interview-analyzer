/**
 * Centralized Authentication Guard & Session Management
 * Provides consistent auth checks, redirects, and authenticated app navbar rendering.
 */
const Auth = {
    _cachedUser: null,

    isAuthenticated() {
        return Boolean(localStorage.getItem("auth_token"));
    },

    async getCurrentUser(forceRefresh = false) {
        if (this._cachedUser && !forceRefresh) {
            return this._cachedUser;
        }
        if (!this.isAuthenticated()) {
            return null;
        }
        try {
            const user = await API.getCurrentUser();
            this._cachedUser = user;
            return user;
        } catch (e) {
            this._cachedUser = null;
            return null;
        }
    },

    async requireAuth(redirectTo = "/login") {
        if (!this.isAuthenticated()) {
            const currentPath = encodeURIComponent(window.location.pathname + window.location.search);
            window.location.href = `${redirectTo}?redirect=${currentPath}`;
            return null;
        }

        const user = await this.getCurrentUser();
        if (!user) {
            API.setToken("");
            const currentPath = encodeURIComponent(window.location.pathname + window.location.search);
            window.location.href = `${redirectTo}?redirect=${currentPath}`;
            return null;
        }
        return user;
    },

    async redirectIfLoggedIn(redirectTo = "/dashboard") {
        if (this.isAuthenticated()) {
            const user = await this.getCurrentUser();
            if (user) {
                const params = new URLSearchParams(window.location.search);
                const dest = params.get("redirect") ? decodeURIComponent(params.get("redirect")) : redirectTo;
                window.location.href = dest;
                return true;
            }
        }
        return false;
    },

    logout() {
        this._cachedUser = null;
        API.setToken("");
        window.location.href = "/login";
    },

    /**
     * Initializes a consistent SaaS app header on authenticated pages.
     * @param {string} activePage - 'dashboard' | 'setup' | 'interview' | 'results' | 'history' | 'profile'
     */
    async initAppNavbar(activePage = "") {
        const user = await this.getCurrentUser();
        const userNameElem = document.getElementById("appUserName");
        const userEmailElem = document.getElementById("appUserEmail");
        const userAvatarElem = document.getElementById("appUserAvatar");
        const logoutBtn = document.getElementById("appLogoutBtn");

        if (user) {
            if (userNameElem) userNameElem.textContent = user.name || "Candidate";
            if (userEmailElem) userEmailElem.textContent = user.email || "";
            if (userAvatarElem) {
                const initial = (user.name || "U").trim().charAt(0).toUpperCase();
                userAvatarElem.textContent = initial;
            }
        }

        if (logoutBtn) {
            logoutBtn.onclick = (e) => {
                e.preventDefault();
                Auth.logout();
            };
        }

        // Highlight active nav item
        if (activePage) {
            document.querySelectorAll(".app-nav-link").forEach(link => {
                if (link.dataset.nav === activePage) {
                    link.classList.add("active");
                } else {
                    link.classList.remove("active");
                }
            });
        }
    }
};

window.Auth = Auth;
