(function () {
  "use strict";

  var DATA_URL = "data/recommendations.json";

  function el(tag, text, className) {
    var node = document.createElement(tag);
    if (text !== undefined && text !== null) node.textContent = text;
    if (className) node.className = className;
    return node;
  }

  function formatPrice(value) {
    if (value === null || value === undefined) return "—";
    var digits = value >= 1 ? 2 : value >= 0.01 ? 4 : 8;
    return "$" + Number(value).toLocaleString("en-US", {
      minimumFractionDigits: Math.min(digits, 2),
      maximumFractionDigits: digits
    });
  }

  function pctCell(value) {
    if (value === null || value === undefined) return el("td", "—");
    var sign = value > 0 ? "+" : "";
    return el("td", sign + Number(value).toFixed(1) + "%", value >= 0 ? "up" : "down");
  }

  function formatDate(iso) {
    if (!iso) return "—";
    var date = new Date(iso);
    if (isNaN(date.getTime())) return iso;
    return date.toLocaleString("en-US", {
      timeZone: "America/New_York",
      dateStyle: "medium",
      timeStyle: "short"
    }) + " ET";
  }

  function safeUrl(url) {
    return typeof url === "string" && /^https:\/\//.test(url) ? url : null;
  }

  function symbolCell(item, withIcon) {
    var td = el("td");
    var icon = withIcon ? safeUrl(item.image) : null;
    if (icon) {
      var img = el("img", null, "coin-icon");
      img.src = icon;
      img.alt = "";
      img.loading = "lazy";
      td.appendChild(img);
    }
    var url = safeUrl(item.url);
    if (url) {
      var link = el("a", item.symbol);
      link.href = url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      td.appendChild(link);
    } else {
      td.appendChild(document.createTextNode(item.symbol));
    }
    return td;
  }

  function notesCell(item) {
    var td = el("td", item.rationale || "", "notes");
    if (item.ai_summary) td.appendChild(el("span", "AI: " + item.ai_summary, "ai"));
    return td;
  }

  function riskCell(risk) {
    var cls = risk === "Very High" ? "risk-very-high" : risk === "High" ? "risk-high" : "";
    return el("td", risk || "—", cls);
  }

  function emptyRow(tbody, columns, message) {
    var tr = el("tr");
    var td = el("td", message);
    td.colSpan = columns;
    tr.appendChild(td);
    tbody.appendChild(tr);
  }

  function renderStocks(items) {
    var tbody = document.querySelector("#stocks-table tbody");
    tbody.replaceChildren();
    if (!items || !items.length) return emptyRow(tbody, 11, "No penny stock recommendations available.");
    items.forEach(function (item) {
      var tr = el("tr");
      tr.appendChild(el("td", item.rank));
      tr.appendChild(symbolCell(item, false));
      tr.appendChild(el("td", item.name));
      tr.appendChild(el("td", formatPrice(item.price)));
      tr.appendChild(pctCell(item.change_1w));
      tr.appendChild(pctCell(item.change_1m));
      tr.appendChild(el("td", item.rsi === null || item.rsi === undefined ? "—" : Number(item.rsi).toFixed(0)));
      tr.appendChild(el("td", item.volume_ratio === undefined ? "—" : Number(item.volume_ratio).toFixed(2) + "×"));
      tr.appendChild(riskCell(item.risk));
      tr.appendChild(el("td", item.score, "score"));
      tr.appendChild(notesCell(item));
      tbody.appendChild(tr);
    });
  }

  function renderCrypto(items) {
    var tbody = document.querySelector("#crypto-table tbody");
    tbody.replaceChildren();
    if (!items || !items.length) return emptyRow(tbody, 11, "No cryptocurrency recommendations available.");
    items.forEach(function (item) {
      var tr = el("tr");
      tr.appendChild(el("td", item.rank));
      tr.appendChild(symbolCell(item, true));
      tr.appendChild(el("td", item.name));
      tr.appendChild(el("td", formatPrice(item.price)));
      tr.appendChild(pctCell(item.change_1d));
      tr.appendChild(pctCell(item.change_1w));
      tr.appendChild(pctCell(item.change_1m));
      tr.appendChild(el("td", item.market_cap_rank ? "#" + item.market_cap_rank : "—"));
      tr.appendChild(riskCell(item.risk));
      tr.appendChild(el("td", item.score, "score"));
      tr.appendChild(notesCell(item));
      tbody.appendChild(tr);
    });
  }

  function render(report) {
    var status = document.getElementById("status");
    if (report.schedule) document.getElementById("schedule").textContent = "Refreshed " + report.schedule.charAt(0).toLowerCase() + report.schedule.slice(1);
    document.getElementById("generated-at").textContent = formatDate(report.generated_at);
    document.getElementById("next-refresh").textContent = formatDate(report.next_refresh);
    if (report.disclaimer) document.getElementById("disclaimer").textContent = report.disclaimer;
    if (report.methodology) {
      document.getElementById("methodology-stocks").textContent = "Penny stocks: " + (report.methodology.penny_stocks || "");
      document.getElementById("methodology-crypto").textContent = "Cryptocurrencies: " + (report.methodology.crypto || "");
    }
    renderStocks(report.penny_stocks);
    renderCrypto(report.crypto);
    status.className = "status";
    status.textContent = report.errors && report.errors.length ? "Some data sources were unavailable: " + report.errors.join("; ") : "";
  }

  function showError(message) {
    var status = document.getElementById("status");
    status.className = "status error";
    status.textContent = message;
  }

  fetch(DATA_URL, { cache: "no-cache" })
    .then(function (response) {
      return response.json().then(function (body) {
        if (!response.ok) throw new Error(body && body.message ? body.message : "HTTP " + response.status);
        return body;
      }, function () {
        throw new Error("HTTP " + response.status);
      });
    })
    .then(render)
    .catch(function (error) {
      showError("Recommendations are not available yet (" + error.message + "). The research agent runs every Monday at 7:00 PM Eastern Time.");
    });
})();
