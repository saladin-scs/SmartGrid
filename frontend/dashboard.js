import Chart from "chart.js/auto";

export function initializeDashboard() {
  const canvas = document.getElementById("type-distribution-chart");
  const data = document.getElementById("type-distribution-data");
  if (!canvas || !data) return;

  const distribution = JSON.parse(data.textContent);
  new Chart(canvas, {
    type: "bar",
    data: {
      labels: distribution.map((item) => item.label),
      datasets: [
        {
          data: distribution.map((item) => item.count),
          backgroundColor: "#55dfa4",
          hoverBackgroundColor: "#8af2c2",
          borderRadius: 4,
          barThickness: 13,
        },
      ],
    },
    options: {
      indexAxis: "y",
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#14231e",
          borderColor: "#304039",
          borderWidth: 1,
          titleColor: "#eff8f3",
          bodyColor: "#b9c9c1",
          displayColors: false,
          callbacks: { label: (context) => `${context.parsed.x} individu(s)` },
        },
      },
      scales: {
        x: {
          beginAtZero: true,
          ticks: { color: "#93a59b", precision: 0, font: { family: "Segoe UI" } },
          grid: { color: "rgba(151, 177, 163, .1)" },
          border: { display: false },
        },
        y: {
          ticks: { color: "#c5d1ca", font: { family: "Segoe UI", size: 11 } },
          grid: { display: false },
          border: { display: false },
        },
      },
    },
  });
}
