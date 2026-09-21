// Nabla triangle from nabla-esp-ui/components/logo/silver.svg, monochrome ring.
window.customIcons = window.customIcons || {};
window.customIcons.nabla = {
  getIcon: async (name) => name === "logo" ? ({path: "M2.4 6.4574373H21.6L12 23.0851253Z M5.664 8.341908L12 19.3161827L18.336 8.341908Z", viewBox: "0 0 24 24"}) : undefined,
  getIconList: async () => [{name: "logo"}],
};
