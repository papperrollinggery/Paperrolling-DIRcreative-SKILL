(() => {
  const current = window.location.hash;
  if (current) {
    const target = document.querySelector(current);
    target?.setAttribute("tabindex", "-1");
  }
})();
