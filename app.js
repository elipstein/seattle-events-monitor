const DATA_URL = "data/events.json";
const REFRESH_MS = 5 * 60 * 1000;
const SOON_DAYS = 14;

function formatDate(iso) {
  if (!iso) return "TBD";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "TBD";
  return d.toLocaleDateString("en-US", { month: "short", day: "2-digit" });
}

function isSoon(iso) {
  if (!iso) return false;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return false;
  const days = (d - new Date()) / (1000 * 60 * 60 * 24);
  return days >= 0 && days <= SOON_DAYS;
}

function badgeText(event) {
  if (event.lane === "big" && event.flight_hours != null) {
    return `${event.flight_hours}h flight • ${event.category}`;
  }
  return event.category || "";
}

function renderRow(event) {
  const row = document.createElement("div");
  row.className = "row" + (isSoon(event.start) ? " soon" : "");

  const date = document.createElement("span");
  date.className = "date";
  date.textContent = formatDate(event.start);

  const titleCell = document.createElement("span");
  titleCell.className = "title-cell";
  const titleLink = document.createElement(event.url ? "a" : "span");
  if (event.url) {
    titleLink.href = event.url;
    titleLink.target = "_blank";
    titleLink.rel = "noopener noreferrer";
  }
  titleLink.textContent = event.title;
  titleCell.appendChild(titleLink);

  const venue = document.createElement("span");
  venue.className = "venue";
  venue.textContent = [event.venue, event.city].filter(Boolean).join(" — ");
  titleCell.appendChild(venue);

  const badge = document.createElement("span");
  badge.className = "badge";
  badge.textContent = badgeText(event);

  row.append(date, titleCell, badge);
  return row;
}

async function loadEvents() {
  const lastUpdated = document.getElementById("last-updated");
  try {
    const resp = await fetch(`${DATA_URL}?t=${Date.now()}`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();

    lastUpdated.textContent = `updated ${new Date(data.generated_at).toLocaleString("en-US")}`;

    const local = data.events.filter((e) => e.lane === "local");
    const big = data.events.filter((e) => e.lane === "big");

    renderLane("rows-local", "empty-local", local);
    renderLane("rows-big", "empty-big", big);
  } catch (err) {
    lastUpdated.textContent = "couldn't load data/events.json";
    console.error(err);
  }
}

function renderLane(rowsId, emptyId, events) {
  const container = document.getElementById(rowsId);
  const empty = document.getElementById(emptyId);
  container.innerHTML = "";
  if (events.length === 0) {
    empty.hidden = false;
    return;
  }
  empty.hidden = true;
  for (const event of events) {
    container.appendChild(renderRow(event));
  }
}

loadEvents();
setInterval(loadEvents, REFRESH_MS);
