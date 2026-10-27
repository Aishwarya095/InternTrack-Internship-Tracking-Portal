/**
 * INTERNTRACK — Core App Controller & Navigation
 */

let currentRole = "STUDENT";
let currentUSN = "1KG21CS045";
let currentStudentName = "Student";
let currentView = "dashboard";

document.addEventListener("DOMContentLoaded", () => {
  initApp();
});

function initApp() {
  loadDashboardStats();
  loadStudentProfile();
  loadSubmissions();
  loadOpportunities();
  loadStudentsDirectory();
  loadTrackingCards();
  loadEvaluations();
  loadAuditTrail();
  loadNotifications();
}

function switchView(viewName) {
  currentView = viewName;
  document.querySelectorAll(".view-panel").forEach(p => p.classList.remove("active"));
  document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));

  const targetPanel = document.getElementById(`view-${viewName}`);
  const targetBtn = document.querySelector(`.nav-btn[data-view="${viewName}"]`);
  
  if (targetPanel) targetPanel.classList.add("active");
  if (targetBtn) targetBtn.classList.add("active");

  const titles = {
    "dashboard": "Operational Dashboard",
    "form": "Internship Preference Form",
    "submissions": "My Submission History",
    "review-queue": "Coordinator Review Queue",
    "hod-queue": "HOD Departmental Sanction",
    "opportunities": "Opportunities & Vacancies",
    "students": "Student Database Directory",
    "tracking": "3–4 Month Progress Journals",
    "evaluation": "Final Evaluation & Credits",
    "audit": "Immutable System Audit Trail",
    "chat": "1-on-1 AURA Assistant",
    "studio": "14-Lab Studio (LangGraph Engine)",
    "resume-matcher": "Resume / CV Skills Auto-Matcher"
  };
  document.getElementById("currentViewTitle").innerText = titles[viewName] || "InternTrack";

  // Trigger relevant view refreshes
  if (viewName === "dashboard") loadDashboardStats();
  if (viewName === "review-queue") loadCoordinatorReviewQueue();
  if (viewName === "hod-queue") loadHODReviewQueue();
  if (viewName === "submissions") loadSubmissions();
  if (viewName === "opportunities") loadOpportunities();
  if (viewName === "tracking") loadTrackingCards();
  if (viewName === "evaluation") loadEvaluations();
  if (viewName === "audit") loadAuditTrail();
  if (viewName === "studio" && typeof loadLabDemo === "function") loadLabDemo(typeof activeLab !== "undefined" ? activeLab : 1);
}

function setRole(role) {
  currentRole = role;
  document.querySelectorAll(".role-chip").forEach(c => c.classList.remove("active"));

  if (role === "STUDENT") {
    document.getElementById("roleBtnStudent").classList.add("active");
    currentUSN = (typeof currentUSN !== "undefined" && currentUSN) ? currentUSN : "1KG21CS045";
    currentStudentName = "Student";
    document.getElementById("userNameText").innerText = "Student";
    document.getElementById("userRoleText").innerText = "Student Applicant";
    document.getElementById("userAvatarText").innerText = "ST";
    if (typeof showToast === "function") {
      showToast("Role switched to STUDENT: Fill & submit internship preferences.", "info");
    }
    switchView("form"); // Directs student to fill application form!
  } else if (role === "COORDINATOR") {
    document.getElementById("roleBtnCoord").classList.add("active");
    currentStudentName = "Internship Coordinator";
    document.getElementById("userNameText").innerText = "Coordinator";
    document.getElementById("userRoleText").innerText = "Review & Credit Clearance";
    document.getElementById("userAvatarText").innerText = "CO";
    if (typeof showToast === "function") {
      showToast("Role switched to COORDINATOR: Review applications & sign off credits.", "info");
    }
    switchView("review-queue"); // Directs coordinator to application review desk!
  } else if (role === "HOD") {
    document.getElementById("roleBtnHOD").classList.add("active");
    currentStudentName = "Prof. S. H. Patil (HOD)";
    document.getElementById("userNameText").innerText = "HOD";
    document.getElementById("userRoleText").innerText = "Departmental Sanction & Credits";
    document.getElementById("userAvatarText").innerText = "HD";
    if (typeof showToast === "function") {
      showToast("Role switched to HOD: Grant final departmental sanctions & award 12 credits.", "info");
    }
    switchView("hod-queue"); // Directs HOD to departmental sanction desk!
  }

  loadDashboardStats();
  loadSubmissions();
  if (typeof loadEvaluations === "function") loadEvaluations();
}

async function loadDashboardStats() {
  try {
    const res = await fetch("/api/dashboard/stats");
    const data = await res.json();
    document.getElementById("statTotalStudents").innerText = data.total_students;
    document.getElementById("statPendingReviews").innerText = data.pending_reviews;
    document.getElementById("statApprovedInternships").innerText = data.approved_internships;
    document.getElementById("statRejectedApps").innerText = data.rejected_applications;
    document.getElementById("statPlacedStudents").innerText = data.placed_company_students;
    document.getElementById("statAvailVacancies").innerText = `${data.available_vacancies} / ${data.total_vacancies}`;
    document.getElementById("badgePendingCount").innerText = `${data.pending_reviews} Pending`;
  } catch (err) {
    console.error("Failed to load dashboard stats:", err);
  }
}

async function loadStudentProfile() {
  try {
    const res = await fetch(`/api/students/profile?usn=${currentUSN}`);
    const data = await res.json();
    if (data && !data.error) {
      if (document.getElementById("userNameText")) document.getElementById("userNameText").innerText = "Student";
      if (document.getElementById("userRoleText")) document.getElementById("userRoleText").innerText = "Student";
      if (document.getElementById("userAvatarText")) document.getElementById("userAvatarText").innerText = "ST";
    }
  } catch (err) {
    console.error("Failed to load student profile:", err);
  }
}

async function loadNotifications() {
  try {
    const res = await fetch(`/api/notifications?recipient=${currentRole === 'STUDENT' ? currentUSN : currentRole}`);
    const data = await res.json();
    document.getElementById("notifBadge").innerText = data.length || 0;
  } catch (err) {
    console.error("Failed to load notifications:", err);
  }
}

function toggleNotifDrawer() {
  alert("In-App Notifications:\n- System initialized with 8th-sem academic seed data.\n- 50 opportunities currently active.\n- Student profile loaded.");
}

// AURA Chat
async function handleChatSubmit(e) {
  e.preventDefault();
  const input = document.getElementById("chatInput");
  const msg = input.value.trim();
  if (!msg) return;

  const chatContainer = document.getElementById("chatMessages");
  chatContainer.innerHTML += `
    <div class="chat-bubble user">
      ${msg}
    </div>
  `;
  input.value = "";
  chatContainer.scrollTop = chatContainer.scrollHeight;

  try {
    const res = await fetch("/api/aura/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: jsonStringify({ message: msg, student_usn: currentUSN })
    });
    const data = await res.json();

    let traceHtml = "";
    if (data.tool_trace && data.tool_trace.length > 0) {
      traceHtml = `
        <div class="trace-box">
          <div style="font-weight:700; color:#cbd5e1; margin-bottom:4px;">⚡ AURA Tool Execution Trace:</div>
          ${data.tool_trace.map(t => `<div>• <strong>${t.tool}</strong>(${JSON.stringify(t.input)}) → <em>${JSON.stringify(t.output).substring(0, 90)}...</em> (${t.duration_ms}ms)</div>`).join("")}
        </div>
      `;
    }

    let planHtml = "";
    if (data.plan && data.plan.phases) {
      planHtml = `
        <div style="margin-top:0.75rem; padding:0.75rem; background:rgba(0,0,0,0.3); border-radius:6px; font-size:0.82rem;">
          <div style="font-weight:700; color:#38bdf8; margin-bottom:4px;">📋 ${data.plan.title} (v${data.plan.version})</div>
          ${data.plan.phases.map(p => `<div><strong>${p.phase_id}:</strong> ${p.title} (${p.duration})</div>`).join("")}
        </div>
      `;
    }

    chatContainer.innerHTML += `
      <div class="chat-bubble aura">
        <div style="font-weight:700; color:var(--primary-light); margin-bottom:0.25rem;">AURA Assistant</div>
        <div>${data.reply.replace(/\n/g, "<br>")}</div>
        ${planHtml}
        ${traceHtml}
      </div>
    `;
    chatContainer.scrollTop = chatContainer.scrollHeight;
  } catch (err) {
    console.error("Chat error:", err);
  }
}

function jsonStringify(obj) {
  return JSON.stringify(obj);
}
