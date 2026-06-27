const state = {
  sessionId: null,
  total: 0,
  recorder: null,
  chunks: [],
  recording: false,
  busy: false,
};

const el = (id) => document.getElementById(id);
const player = el("player");

async function loadConfig() {
  const res = await fetch("/api/config");
  const cfg = await res.json();
  el("role-title").textContent = cfg.role_title || "Voice Interview Agent";
  state.total = cfg.total_questions;
  const select = el("language");
  select.innerHTML = "";
  for (const [code, name] of Object.entries(cfg.languages)) {
    const opt = document.createElement("option");
    opt.value = code;
    opt.textContent = name;
    if (code === cfg.default_language) opt.selected = true;
    select.appendChild(opt);
  }
}

function addBubble(role, text) {
  const log = el("log");
  const bubble = document.createElement("div");
  bubble.className = `bubble ${role}`;
  const who = document.createElement("div");
  who.className = "who";
  who.textContent = role === "agent" ? "Interviewer" : "You";
  const body = document.createElement("div");
  body.textContent = text;
  bubble.appendChild(who);
  bubble.appendChild(body);
  log.appendChild(bubble);
  bubble.scrollIntoView({ behavior: "smooth", block: "end" });
}

function playAudio(b64) {
  if (!b64) return;
  player.src = `data:audio/mp3;base64,${b64}`;
  player.play().catch(() => {});
}

function setProgress(current) {
  el("progress-label").textContent = `Question ${current} of ${state.total}`;
  el("progress-fill").style.width = `${(current / state.total) * 100}%`;
}

function setStatus(text) {
  el("status").textContent = text || "";
}

function setOrbState(mode) {
  const orb = el("record-btn");
  orb.classList.remove("recording", "thinking");
  const label = orb.querySelector(".orb-label");
  if (mode === "recording") {
    orb.classList.add("recording");
    label.textContent = "Listening…";
  } else if (mode === "thinking") {
    orb.classList.add("thinking");
    label.textContent = "Thinking…";
  } else {
    label.textContent = "Hold to answer";
  }
}

async function startInterview() {
  const language = el("language").value;
  const candidateName = el("candidate-name").value.trim();
  el("start-btn").disabled = true;
  el("start-btn").textContent = "Connecting…";
  try {
    const res = await fetch("/api/session/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ language, candidate_name: candidateName }),
    });
    if (!res.ok) throw new Error("start failed");
    const data = await res.json();
    state.sessionId = data.session_id;
    el("setup").classList.add("hidden");
    el("interview").classList.remove("hidden");
    setProgress(data.question_number);
    addBubble("agent", data.reply_text);
    playAudio(data.reply_audio_b64);
    el("record-btn").disabled = false;
  } catch (err) {
    el("start-btn").disabled = false;
    el("start-btn").textContent = "Start interview";
    alert("Could not start the interview. Check the server and API key.");
  }
}

async function setupRecorder() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const recorder = new MediaRecorder(stream);
  recorder.ondataavailable = (e) => {
    if (e.data.size > 0) state.chunks.push(e.data);
  };
  recorder.onstop = sendAnswer;
  state.recorder = recorder;
}

async function startRecording() {
  if (state.busy || state.recording) return;
  if (!state.recorder) {
    try {
      await setupRecorder();
    } catch (err) {
      setStatus("Microphone access was blocked.");
      return;
    }
  }
  state.chunks = [];
  state.recording = true;
  state.recorder.start();
  setOrbState("recording");
}

function stopRecording() {
  if (!state.recording) return;
  state.recording = false;
  state.recorder.stop();
}

async function sendAnswer() {
  state.busy = true;
  setOrbState("thinking");
  setStatus("");
  const blob = new Blob(state.chunks, { type: "audio/webm" });
  const form = new FormData();
  form.append("audio", blob, "answer.webm");
  try {
    const res = await fetch(`/api/session/${state.sessionId}/respond`, {
      method: "POST",
      body: form,
    });
    if (!res.ok) throw new Error("respond failed");
    const data = await res.json();
    if (data.transcript) addBubble("user", data.transcript);
    addBubble("agent", data.reply_text);
    playAudio(data.reply_audio_b64);
    setProgress(data.question_number);
    if (data.finished) {
      await loadFeedback();
    }
  } catch (err) {
    setStatus("Something went wrong. Try answering again.");
  } finally {
    state.busy = false;
    setOrbState("idle");
  }
}

async function loadFeedback() {
  el("record-btn").disabled = true;
  setStatus("Preparing your feedback…");
  try {
    const res = await fetch(`/api/session/${state.sessionId}/feedback`, { method: "POST" });
    const data = await res.json();
    renderFeedback(data);
    playAudio(data.reply_audio_b64);
  } catch (err) {
    setStatus("Could not load feedback.");
  }
}

function renderFeedback(data) {
  el("interview").classList.add("hidden");
  el("feedback").classList.remove("hidden");
  el("overall-score").textContent = Number(data.overall_score).toFixed(1);
  el("feedback-summary").textContent = data.summary;
  fillList("strengths", data.strengths);
  fillList("improvements", data.improvements);
  const wrap = el("per-question");
  wrap.innerHTML = "";
  for (const item of data.per_question) {
    const row = document.createElement("div");
    row.className = "pq-row";
    row.innerHTML = `
      <div class="pq-score">${item.score}</div>
      <div class="pq-body">
        <div class="q"></div>
        <div class="c"></div>
      </div>`;
    row.querySelector(".q").textContent = item.question;
    row.querySelector(".c").textContent = item.comment;
    wrap.appendChild(row);
  }
}

function fillList(id, items) {
  const ul = el(id);
  ul.innerHTML = "";
  for (const text of items || []) {
    const li = document.createElement("li");
    li.textContent = text;
    ul.appendChild(li);
  }
}

function bindRecordButton() {
  const orb = el("record-btn");
  orb.addEventListener("mousedown", startRecording);
  orb.addEventListener("mouseup", stopRecording);
  orb.addEventListener("mouseleave", () => state.recording && stopRecording());
  orb.addEventListener("touchstart", (e) => { e.preventDefault(); startRecording(); });
  orb.addEventListener("touchend", (e) => { e.preventDefault(); stopRecording(); });
}

el("start-btn").addEventListener("click", startInterview);
el("finish-btn").addEventListener("click", loadFeedback);
el("restart-btn").addEventListener("click", () => window.location.reload());
bindRecordButton();
loadConfig();
