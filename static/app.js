// static/app.js

const ROOMS = ["R1", "R2", "R3", "R4", "R5", "R6"];

function showApp(username) {
  document.getElementById("login-screen").classList.add("hidden");
  const app = document.getElementById("app");
  app.style.display = "block";
  document.getElementById("user-label").textContent =
    `Logged in as ${username || "Operator"}`;
}

// --- LOGIN ---

window.addEventListener("load", () => {
  const loginBtn = document.getElementById("login-btn");
  const loginInput = document.getElementById("login-id");

  loginBtn.addEventListener("click", () => {
    const val = loginInput.value.trim() || "Operator";
    localStorage.setItem("safepath_user", val);
    showApp(val);
    initCameraWall();
  });

  loginInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") loginBtn.click();
  });

  const saved = localStorage.getItem("safepath_user");
  if (saved) {
    showApp(saved);
    initCameraWall();
  }

  setupFloorplanUpload();
  setup3DUpload();
  load3DIfExists();
  startRoomStatePolling();
});

// --- FLOORPLAN UPLOAD ---

function setupFloorplanUpload() {
  const fileInput = document.getElementById("floorplan-file");
  const fileLabel = document.getElementById("file-label");
  const uploadBtn = document.getElementById("upload-btn");
  const statusEl = document.getElementById("upload-status");
  const mapBase = document.getElementById("map-base");

  if (!fileInput || !uploadBtn) return;

  fileInput.addEventListener("change", () => {
    fileLabel.textContent = fileInput.files.length
      ? fileInput.files[0].name
      : "Choose floorplan PNG…";
  });

  uploadBtn.addEventListener("click", async () => {
    if (!fileInput.files.length) {
      statusEl.textContent = "Select a PNG/JPG first.";
      return;
    }
    const fd = new FormData();
    fd.append("file", fileInput.files[0]);
    statusEl.textContent = "Uploading floorplan...";
    try {
      const res = await fetch("/api/upload_floorplan", { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) {
        statusEl.textContent = data.error || "Upload failed.";
        return;
      }
      statusEl.textContent = "Floorplan updated.";
      const ts = Date.now();
      mapBase.src = `floorplan.png?ts=${ts}`;
    } catch (err) {
      console.error(err);
      statusEl.textContent = "Upload error. Check console.";
    }
  });
}

// --- 3D UPLOAD + DISPLAY ---

function setup3DUpload() {
  const fileInput = document.getElementById("threeD-file");
  const fileLabel = document.getElementById("threeD-label");
  const uploadBtn = document.getElementById("threeD-upload-btn");
  const statusEl = document.getElementById("threeD-status");
  const img = document.getElementById("threeD-img");

  if (!fileInput || !uploadBtn) return;

  fileInput.addEventListener("change", () => {
    fileLabel.textContent = fileInput.files.length
      ? fileInput.files[0].name
      : "Choose 3D PNG/JPG…";
  });

  uploadBtn.addEventListener("click", async () => {
    if (!fileInput.files.length) {
      statusEl.textContent = "Select a PNG/JPG first.";
      return;
    }
    const fd = new FormData();
    fd.append("file", fileInput.files[0]);
    statusEl.textContent = "Uploading 3D layout...";
    try {
      const res = await fetch("/api/upload_3d", { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) {
        statusEl.textContent = data.error || "Upload failed.";
        return;
      }
      statusEl.textContent = "3D layout updated.";
      const ts = Date.now();
      img.src = `building3d.png?ts=${ts}`;
      img.style.display = "block";
    } catch (err) {
      console.error(err);
      statusEl.textContent = "Upload error. Check console.";
    }
  });
}

function load3DIfExists() {
  const img = document.getElementById("threeD-img");
  if (!img) return;
  const ts = Date.now();
  img.onload = () => { img.style.display = "block"; };
  img.onerror = () => { img.style.display = "none"; };
  img.src = `building3d.png?ts=${ts}`;
}

// --- CAMERA WALL (R5 uses browser webcam) ---

function initCameraWall() {
  const video = document.getElementById("cam-R5");
  if (!video) return;
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    console.warn("getUserMedia not supported; R5 webcam disabled.");
    return;
  }
  navigator.mediaDevices.getUserMedia({ video: true })
    .then(stream => {
      video.srcObject = stream;
      video.play().catch(() => {});
    })
    .catch(err => {
      console.warn("Unable to start webcam for R5:", err);
    });
}

// --- ROOM STATES / MAP COLORING ---

async function fetchRoomStates() {
  try {
    const res = await fetch("/api/room_states");
    if (!res.ok) throw new Error("Failed to fetch room states");
    return await res.json();
  } catch (err) {
    console.error("Error fetching room states:", err);
    return null;
  }
}

function applyRoomStates(states) {
  const pre = document.getElementById("room-states");
  if (!states) {
    if (pre) pre.textContent = "No data from engine.";
    return;
  }

  const lines = [];

  ROOMS.forEach((id) => {
    const zone = document.getElementById(`zone-${id}`);
    const raw = states[id] || "clear";

    let cls;
    if (raw === "fire" || raw === "fire_gun") {
      cls = "fire";
    } else if (raw === "gun") {
      cls = "gun";
    } else {
      cls = "safe";
    }

    if (zone) {
      zone.classList.remove("safe", "fire", "gun");
      zone.classList.add(cls);
    }

    lines.push(`${id}: ${raw}`);
  });

  if (pre) pre.textContent = lines.join("\n");
}

function startRoomStatePolling() {
  const tick = async () => {
    const s = await fetchRoomStates();
    applyRoomStates(s);
  };
  tick();
  setInterval(tick, 1000);
}
