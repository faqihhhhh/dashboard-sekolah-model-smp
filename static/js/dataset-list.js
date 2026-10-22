document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("[data-auto-submit-filter]");
  if (!form) return;

  let searchTimer;
  const search = form.querySelector('input[name="q"]');

  form.querySelectorAll("select").forEach((select) => {
    select.addEventListener("change", () => form.requestSubmit());
  });

  form.querySelectorAll("[data-multi-filter]").forEach((filter) => {
    let wasOpen = false;
    filter.addEventListener("toggle", () => {
      if (filter.open) {
        wasOpen = true;
      } else if (wasOpen) {
        wasOpen = false;
        form.requestSubmit();
      }
    });
  });

  document.addEventListener("click", (event) => {
    if (event.target.closest(".filter-reset")) return;
    form.querySelectorAll("[data-multi-filter][open]").forEach((filter) => {
      if (!filter.contains(event.target)) filter.open = false;
    });
  });

  if (search) {
    search.addEventListener("input", () => {
      window.clearTimeout(searchTimer);
      searchTimer = window.setTimeout(() => form.requestSubmit(), 350);
    });
  }

  form.querySelectorAll("[data-remove-province]").forEach((button) => {
    button.addEventListener("click", () => {
      const value = button.dataset.removeProvince;
      const checkbox = form.querySelector(
        `input[name="provinsi"][value="${CSS.escape(value)}"]`
      );
      if (checkbox) checkbox.checked = false;
      form.requestSubmit();
    });
  });

  document.querySelectorAll(".row-actions").forEach((menu) => {
    menu.addEventListener("toggle", () => {
      if (!menu.open) return;
      document.querySelectorAll(".row-actions[open]").forEach((otherMenu) => {
        if (otherMenu !== menu) otherMenu.open = false;
      });
    });
  });
});
