const TOKEN_KEY = "sniplink_token";
const USERNAME_KEY = "sniplink_username";

export const getAuthToken = (): string | null => {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
};

export const getAuthUsername = (): string | null => {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(USERNAME_KEY);
};

export const setAuth = (token: string, username: string) => {
  window.localStorage.setItem(TOKEN_KEY, token);
  window.localStorage.setItem(USERNAME_KEY, username);

  // Default to dark mode on first login (do not override an existing preference).
  const theme = window.localStorage.getItem("theme");
  if (!theme) {
    window.localStorage.setItem("theme", "dark");
    document.documentElement.classList.add("dark");
  }
};

export const clearAuth = () => {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(USERNAME_KEY);
};
