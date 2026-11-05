// Butun sayt uchun umumiy JavaScript.

// 1) data-confirm="..." bo'lgan formalarda tasdiqlash so'raladi.
// 2) POST formasi yuborilgach, tugmalar o'chiriladi — ikki marta bosib
//    ikki marta saqlab qo'yishning oldini oladi (server ham alohida tekshiradi).
document.addEventListener("submit", function (event) {
  const form = event.target;
  if (form.dataset.confirm && !window.confirm(form.dataset.confirm)) {
    event.preventDefault();
    return;
  }
  if (form.method.toLowerCase() !== "post") return;
  if (form.dataset.submitted) {
    event.preventDefault();
    return;
  }
  form.dataset.submitted = "1";
  // setTimeout: tugma o'chishidan oldin forma ma'lumotlari yuborilib ulgursin
  setTimeout(function () {
    form.querySelectorAll("button[type=submit], button:not([type])").forEach(function (btn) {
      btn.disabled = true;
    });
  }, 0);
});

// "Orqaga" tugmasi bilan qaytilganda tugmalarni qayta yoqamiz
window.addEventListener("pageshow", function (event) {
  if (!event.persisted) return;
  document.querySelectorAll("form[data-submitted]").forEach(function (form) {
    delete form.dataset.submitted;
    form.querySelectorAll("button").forEach(function (btn) { btn.disabled = false; });
  });
});
