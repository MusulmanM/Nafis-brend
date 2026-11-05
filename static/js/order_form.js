// Buyurtma formasi:
//  1) telefon yozilganda mijozni serverdan qidiradi (topilsa — kartasini ko'rsatadi,
//     topilmasa — yangi mijoz maydonlarini ochadi);
//  2) mahsulot sonini [-] [+] tugmalari bilan o'zgartirish;
//  3) jami summani darhol hisoblash.
(function () {
  const form = document.querySelector("[data-qty-form]");
  if (!form) return;

  const formatSom = (n) => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, " ") + " so'm";
  const show = (el, visible) => el && el.classList.toggle("d-none", !visible);

  // --- Jami summa ---
  const totalEl = document.getElementById("order-total");
  const qtyInputs = form.querySelectorAll("input[data-price]");
  function updateTotal() {
    let total = 0;
    qtyInputs.forEach((input) => {
      const qty = Math.max(0, parseInt(input.value, 10) || 0);
      total += qty * parseInt(input.dataset.price, 10);
    });
    totalEl.textContent = formatSom(total);
  }
  qtyInputs.forEach((input) => input.addEventListener("input", updateTotal));
  form.querySelectorAll("[data-step]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const input = document.getElementById(btn.dataset.target);
      const next = (parseInt(input.value, 10) || 0) + parseInt(btn.dataset.step, 10);
      input.value = Math.min(1000, Math.max(0, next));
      updateTotal();
    });
  });
  updateTotal();

  // --- Mijozni telefon bo'yicha qidirish ---
  const phoneInput = document.getElementById("id_phone");
  const foundBox = document.getElementById("found-customer");
  const newBox = document.getElementById("new-customer");
  // Tahrirlash rejimida va doimiy buyurtma formasida bu qism kerak emas
  if (!phoneInput || !form.dataset.lookupUrl) return;

  let timer = null;
  let lastQuery = null;

  async function lookup() {
    const value = phoneInput.value.trim();
    const digits = value.replace(/\D/g, "");
    const complete = digits.length === 9 || (digits.length === 12 && digits.startsWith("998"));
    if (!complete) {
      show(foundBox, false);
      show(newBox, false);
      lastQuery = null;
      return;
    }
    if (digits === lastQuery) return;
    lastQuery = digits;

    try {
      const response = await fetch(form.dataset.lookupUrl + "?phone=" + encodeURIComponent(value), {
        headers: { Accept: "application/json" },
      });
      const data = await response.json();
      if (data.found) {
        // Ma'lumotlarni textContent bilan qo'yamiz (HTML sifatida emas) — xavfsiz
        foundBox.querySelectorAll("[data-field]").forEach((el) => {
          el.textContent = data[el.dataset.field] ?? "";
        });
        foundBox.querySelector("[data-link]").href = data.url;
        show(foundBox, true);
        show(newBox, false);
      } else {
        show(foundBox, false);
        show(newBox, data.valid);
        if (data.valid) document.getElementById("id_name").focus();
      }
    } catch (e) {
      // Tarmoq xatosi: yangi mijoz maydonlarini ochib qo'yamiz, server baribir tekshiradi
      show(newBox, true);
    }
  }

  phoneInput.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(lookup, 300);
  });
})();
