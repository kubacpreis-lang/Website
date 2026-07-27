(() => {
  const narrowScreen = window.matchMedia("(max-width: 980px)");
  const tablesOfContents = document.querySelectorAll("details.booktoc");

  const syncOpenState = () => {
    tablesOfContents.forEach((tableOfContents) => {
      tableOfContents.open = !narrowScreen.matches;
    });
  };

  syncOpenState();
  narrowScreen.addEventListener("change", syncOpenState);
})();
