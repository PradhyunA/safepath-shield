async function fetchPlan(hazards) {
    // If hazards is provided, POST (manual override).
    if (hazards) {
      const res = await fetch("/api/hazards", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ hazards })
      });
      return res.json();
    }
  
    // Otherwise GET current state (used by auto-poll + initial load)
    const res = await fetch("/api/hazards");
    return res.json();
  }
  
  function renderPlan(data) {
    const { hazards, plan } = data;
    const planDiv = document.getElementById("plan");
  
    let html = `<p><strong>Current Hazards:</strong> ${
      hazards && hazards.length ? hazards.join(", ") : "None"
    }</p>`;
  
    html += `<h3>Rooms</h3><ul>`;
    for (const [room, info] of Object.entries(plan.rooms)) {
      if (info.mode === "EVAC") {
        html += `<li>${room}: EVAC to <strong>${info.exit}</strong></li>`;
      } else {
        html += `<li>${room}: <strong>LOCKDOWN</strong></li>`;
      }
    }
    html += `</ul>`;
  
    html += `<h3>Doors</h3><ul>`;
    for (const [door, state] of Object.entries(plan.doors)) {
      html += `<li>${door}: ${state}</li>`;
    }
    html += `</ul>`;
  
    planDiv.innerHTML = html;
  
    drawMap(hazards || [], plan);
  }
  
  function drawMap(hazards, plan) {
    const c = document.getElementById("mapCanvas");
    const ctx = c.getContext("2d");
    ctx.clearRect(0, 0, c.width, c.height);
  
    const pos = {
      R1: { x: 70, y: 60 },
      R2: { x: 70, y: 180 },
      H1: { x: 190, y: 120 },
      H2: { x: 310, y: 120 },
      X1: { x: 380, y: 120 }
    };
  
    const edges = [
      ["R1", "H1"],
      ["R2", "H1"],
      ["H1", "H2"],
      ["H2", "X1"]
    ];
  
    // edges
    ctx.strokeStyle = "#555";
    ctx.lineWidth = 2;
    edges.forEach(([a, b]) => {
      ctx.beginPath();
      ctx.moveTo(pos[a].x, pos[a].y);
      ctx.lineTo(pos[b].x, pos[b].y);
      ctx.stroke();
    });
  
    // nodes
    for (const id in pos) {
      const { x, y } = pos[id];
      const isHazard = hazards.includes(id);
  
      ctx.beginPath();
      ctx.arc(x, y, 12, 0, 2 * Math.PI);
      ctx.fillStyle = isHazard ? "#ff3b3b" : "#1e90ff";
      ctx.fill();
  
      ctx.fillStyle = "#ffffff";
      ctx.font = "9px system-ui";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(id, x, y - 18);
    }
  }
  
  // Manual override from text box (for testing)
  document.getElementById("updateBtn").onclick = async () => {
    const raw = document.getElementById("hazardsInput").value.trim();
    const hazards = raw
      ? raw.split(",").map((s) => s.trim()).filter((s) => s.length)
      : [];
    const data = await fetchPlan(hazards);
    renderPlan(data);
  };
  
  // Initial load
  fetchPlan().then(renderPlan);
  
  // Auto-poll every 1s to reflect YOLO updates
  setInterval(async () => {
    try {
      const data = await fetchPlan();
      renderPlan(data);
    } catch (e) {
      console.error("Poll failed", e);
    }
  }, 1000);
  