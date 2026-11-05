// Saytdagi barcha grafiklar uchun umumiy uslub (Chart.js).
// Bitta rang, ingichka ustunlar (≤24px), yuqori burchaklari yumaloq,
// xira yordamchi chiziqlar, ustiga kelganda oq tooltip.
window.AppCharts = (function () {
  const SERIES = "#2a78d6";
  const SERIES_HOVER = "#5598e7";
  const MUTED = "#898781";
  const GRID = "#e1e0d9";
  const AXIS = "#c3c2b7";

  function som(v) {
    return String(Math.round(v)).replace(/\B(?=(\d{3})+(?!\d))/g, " ") + " so'm";
  }
  function compact(v) {
    if (v >= 1e6) return (Math.round(v / 1e5) / 10).toString().replace(".", ",") + " mln";
    if (v >= 1e3) return Math.round(v / 1e3) + " ming";
    return v;
  }
  function tooltip() {
    return {
      backgroundColor: "#ffffff",
      borderColor: GRID,
      borderWidth: 1,
      titleColor: "#52514e",
      titleFont: { weight: "400" },
      bodyColor: "#0b0b0b",
      bodyFont: { weight: "600", size: 13 },
      padding: 10,
      displayColors: false,
      callbacks: {
        title: function (items) {
          const label = items[0].label;
          return Array.isArray(label) ? label.join(" ") : String(label).replace(",", " ");
        },
        label: function (ctx) { return som(ctx.parsed[ctx.chart.options.indexAxis === "y" ? "x" : "y"]); },
      },
    };
  }
  function setup() {
    Chart.defaults.font.family = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
    Chart.defaults.color = MUTED;
  }
  function dataset(values) {
    return {
      data: values,
      backgroundColor: SERIES,
      hoverBackgroundColor: SERIES_HOVER,
      maxBarThickness: 24,
      borderRadius: 4,          // ma'lumot uchi yumaloq, asos tomoni tekis
      borderSkipped: "start",
    };
  }

  // Vaqt bo'yicha ustunlar (masalan, kunlik tushum)
  function columns(canvas, labels, values) {
    if (!window.Chart || !canvas) return;
    setup();
    return new Chart(canvas, {
      type: "bar",
      data: { labels: labels, datasets: [dataset(values)] },
      options: {
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: { legend: { display: false }, tooltip: tooltip() },
        scales: {
          x: { grid: { display: false }, border: { color: AXIS }, ticks: { maxRotation: 0, autoSkipPadding: 8 } },
          y: { beginAtZero: true, border: { display: false }, grid: { color: GRID }, ticks: { maxTicksLimit: 5, callback: compact } },
        },
      },
    });
  }

  // Gorizontal ustunlar, kattadan kichikka (masalan, to'lov turlari)
  function bars(canvas, labels, values) {
    if (!window.Chart || !canvas) return;
    setup();
    canvas.parentElement.style.height = labels.length * 40 + 36 + "px";
    return new Chart(canvas, {
      type: "bar",
      data: { labels: labels, datasets: [dataset(values)] },
      options: {
        indexAxis: "y",
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false, axis: "y" },
        plugins: { legend: { display: false }, tooltip: tooltip() },
        scales: {
          x: { beginAtZero: true, border: { display: false }, grid: { color: GRID }, ticks: { maxTicksLimit: 5, callback: compact } },
          y: { grid: { display: false }, border: { color: AXIS }, ticks: { color: "#52514e" } },
        },
      },
    });
  }

  return { columns: columns, bars: bars };
})();
