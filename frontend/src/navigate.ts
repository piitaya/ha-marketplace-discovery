export const navigate = (path: string): void => {
  history.pushState({ from: location.pathname }, "", path);
  window.dispatchEvent(new CustomEvent("location-changed", { detail: { replace: false } }));
};
