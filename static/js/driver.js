// Yetkazuvchi paneli: "Yetkazib berdim" va "Olib keldim" formalari uchun yordamchilar.
(function () {
  // Butillar soni: [-] [+] (input'dagi max dan oshmaydi)
  document.querySelectorAll("[data-step]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      const input = document.getElementById(btn.dataset.target);
      const max = parseInt(input.max, 10) || 1000;
      const next = (parseInt(input.value, 10) || 0) + parseInt(btn.dataset.step, 10);
      input.value = Math.max(0, Math.min(max, next));
    });
  });

  // "Hammasi: N ta" kabi tez tanlash tugmalari
  document.querySelectorAll("[data-set]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      document.getElementById(btn.dataset.target).value = btn.dataset.set;
    });
  });

  document.querySelectorAll("[data-delivery-form]").forEach(function (form) {
    const amount = form.querySelector("input[name$='paid_amount']");
    const radios = form.querySelectorAll("input[name$='payment_type']");

    // "Qarzga" tanlansa — summa 0 va o'zgartirib bo'lmaydi
    function syncAmount() {
      const checked = form.querySelector("input[name$='payment_type']:checked");
      const isDebt = checked && checked.value === "debt";
      amount.readOnly = isDebt;
      if (isDebt) amount.value = "0";
      else if (amount.value === "0") amount.value = amount.dataset.lastValue || "";
    }
    radios.forEach(function (radio) { radio.addEventListener("change", syncAmount); });
    amount.addEventListener("input", function () { amount.dataset.lastValue = amount.value; });
    amount.dataset.lastValue = amount.value;

    // Tez to'ldirish: "Buyurtma summasi", "Qarz bilan birga"
    form.querySelectorAll("[data-fill]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const cash = form.querySelector("input[name$='payment_type'][value='cash']");
        const checked = form.querySelector("input[name$='payment_type']:checked");
        if (checked && checked.value === "debt" && cash) { cash.checked = true; syncAmount(); }
        amount.value = btn.dataset.fill;
        amount.dataset.lastValue = amount.value;
      });
    });

    syncAmount();
  });

  // Xato bilan qaytgan oynani avtomatik ochish (agar bo'lsa)
  const invalid = document.querySelector(".modal .is-invalid, .modal .alert-danger");
  if (invalid && window.bootstrap) {
    new bootstrap.Modal(invalid.closest(".modal")).show();
  }
})();
