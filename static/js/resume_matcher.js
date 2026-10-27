/**
 * INTERNTRACK — Resume & CV Skills Auto-Matcher Frontend Controller
 * Provides file upload, drag-and-drop, text analysis, and real-time skill matching.
 */

const SAMPLE_RESUMES = {
  aiml: `ANANYA S. (USN: 1KG21CS045)
B.E. Computer Science & Engineering (8th Sem) | KLE Technological University
CGPA: 8.65 / 10 | Bangalore, Karnataka

TECHNICAL SKILLS:
- Languages: Python, Java, SQL, C++
- AI / ML & Frameworks: PyTorch, TensorFlow, Scikit-learn, Pandas, NumPy, Deep Learning, Natural Language Processing (NLP)
- Cloud & DevOps: Docker, Git, Linux, AWS
- Web & APIs: REST APIs, FastAPI, HTML, CSS

PROJECTS:
1. Multi-Agent Autonomous Healthcare RAG Engine
   - Implemented using LangGraph, Python, PyTorch, and Vector Embeddings.
   - Built custom embeddings evaluation harness achieving 94% retrieval accuracy.
2. End-to-End Real-Time Object Detection Pipeline
   - Built with PyTorch and Docker; deployed on AWS EC2 with continuous integration.`,

  fullstack: `ROHIT VERMA (USN: 1FE23BCS042)
B.E. Computer Science & Engineering | 8th Semester
CGPA: 8.2 | Bengaluru, India

TECHNICAL SKILLS:
- Languages: JavaScript, TypeScript, Python, Java, SQL, HTML5, CSS3
- Frontend: React, Next.js, Redux, TailwindCSS
- Backend: Node.js, Express, Spring Boot, REST APIs
- Databases: PostgreSQL, MongoDB, Redis, SQLite
- Tools & Cloud: Git, Docker, AWS, Postman, CI/CD

PROJECTS:
1. Campus Placement & Internship Management Portal
   - Full-stack web application built with React, Node.js, PostgreSQL, and Docker.
   - Implemented role-based access control and JWT authentication for 500+ students.
2. Distributed E-Commerce Microservices
   - Microservices architecture using Spring Boot, Java, Redis caching, and AWS RDS.`,

  cloud: `PRIYA KULKARNI (USN: 1FE23BCS088)
B.E. Information Science & Engineering | 8th Sem
CGPA: 8.40 | Hubballi / Bengaluru

TECHNICAL SKILLS:
- Cloud Platforms: AWS, Azure, GCP
- DevOps & Containers: Docker, Kubernetes, Terraform, Linux, Shell Scripting, CI/CD, Git
- Programming: Python, Go, Bash, SQL
- Observability: Prometheus, Grafana, CloudWatch

PROJECTS:
1. Automated Multi-Cloud Infrastructure as Code (IaC)
   - Provisioned high-availability Kubernetes clusters on AWS and Azure using Terraform.
2. Microservices CI/CD Pipeline
   - Automated testing and deployment with GitHub Actions, Docker, and Kubernetes.`
};

function loadSampleResume(type) {
  const textarea = document.getElementById("resumeTextInput");
  if (!textarea) return;
  textarea.value = SAMPLE_RESUMES[type] || SAMPLE_RESUMES.aiml;
  const statusEl = document.getElementById("resumeInputStatus");
  if (statusEl) {
    statusEl.innerHTML = `<span style="color:#10b981;"><i class="fa-solid fa-check"></i> Loaded sample <strong>${type.toUpperCase()}</strong> resume. Click 'Auto-Calculate Skill Match' below!</span>`;
  }
}

function clearResumeInput() {
  const textarea = document.getElementById("resumeTextInput");
  const fileInput = document.getElementById("resumeFileInput");
  const statusEl = document.getElementById("resumeInputStatus");
  const resultsContainer = document.getElementById("resumeMatchResultsContainer");
  
  if (textarea) textarea.value = "";
  if (fileInput) fileInput.value = "";
  if (statusEl) statusEl.innerHTML = "";
  if (resultsContainer) resultsContainer.style.display = "none";
}

function handleResumeFileSelect(event) {
  const file = event.target.files && event.target.files[0];
  if (!file) return;
  processSelectedResumeFile(file);
}

function processSelectedResumeFile(file) {
  const statusEl = document.getElementById("resumeInputStatus");
  const textarea = document.getElementById("resumeTextInput");
  
  if (statusEl) {
    statusEl.innerHTML = `<span style="color:#3b82f6;"><i class="fa-solid fa-spinner fa-spin"></i> Reading file: <strong>${escapeHtml(file.name)}</strong> (${(file.size / 1024).toFixed(1)} KB)...</span>`;
  }

  const reader = new FileReader();
  reader.onload = function(e) {
    const text = e.target.result;
    if (textarea) textarea.value = text;
    if (statusEl) {
      statusEl.innerHTML = `<span style="color:#10b981;"><i class="fa-solid fa-file-circle-check"></i> File <strong>${escapeHtml(file.name)}</strong> loaded successfully (${text.length} characters). Ready to calculate match!</span>`;
    }
  };
  reader.onerror = function() {
    if (statusEl) {
      statusEl.innerHTML = `<span style="color:#ef4444;"><i class="fa-solid fa-triangle-exclamation"></i> Error reading file. Please copy-paste the text directly.</span>`;
    }
  };
  reader.readAsText(file);
}

async function runResumeMatch() {
  const textarea = document.getElementById("resumeTextInput");
  const btn = document.getElementById("btnMatchResume");
  const resultsContainer = document.getElementById("resumeMatchResultsContainer");
  const statusEl = document.getElementById("resumeInputStatus");
  const studentUsnInput = document.getElementById("formStudentUSNInput");
  const studentUsn = (studentUsnInput && studentUsnInput.value.trim()) || "1KG21CS045";

  const text = textarea ? textarea.value.trim() : "";
  if (!text || text.length < 20) {
    alert("Please upload a resume or paste at least 20 characters of resume text with skills and projects.");
    if (textarea) textarea.focus();
    return;
  }

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Analyzing Skills & Matching Catalog...`;
  }
  if (statusEl) {
    statusEl.innerHTML = `<span style="color:#818cf8;"><i class="fa-solid fa-microchip fa-spin"></i> Parsing skills against 100+ technical competencies and querying active company catalog...</span>`;
  }

  try {
    const response = await fetch("/api/resume/match", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        resume_text: text,
        student_usn: studentUsn
      })
    });

    const data = await response.json();
    if (!response.ok || data.status !== "SUCCESS") {
      throw new Error(data.message || data.error || "Failed to analyze resume.");
    }

    renderResumeResults(data);
    if (statusEl) {
      statusEl.innerHTML = `<span style="color:#10b981;"><i class="fa-solid fa-circle-check"></i> Analysis complete! Matched across <strong>${data.total_catalog_opportunities} active opportunities</strong>.</span>`;
    }
    if (resultsContainer) {
      resultsContainer.style.display = "block";
      resultsContainer.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  } catch (err) {
    if (statusEl) {
      statusEl.innerHTML = `<span style="color:#ef4444;"><i class="fa-solid fa-circle-exclamation"></i> Error: ${escapeHtml(err.message)}</span>`;
    }
    alert("Resume Match Error: " + err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<i class="fa-solid fa-bolt"></i> Auto-Calculate Skill Match`;
    }
  }
}

function renderResumeResults(data) {
  const profile = data.extracted_profile || {};
  const matches = data.matches || [];
  const detectedSkills = profile.detected_skills || [];

  // 1. Render Metrics Bar
  const detectedCountEl = document.getElementById("resStatDetectedSkills");
  const topCompanyEl = document.getElementById("resStatTopCompany");
  const topScoreEl = document.getElementById("resStatTopScore");
  const detectedCgpaEl = document.getElementById("resStatDetectedCgpa");

  if (detectedCountEl) detectedCountEl.innerText = detectedSkills.length;
  if (topCompanyEl) topCompanyEl.innerText = matches.length > 0 ? matches[0].company_name : "N/A";
  if (topScoreEl) topScoreEl.innerText = matches.length > 0 ? `${matches[0].match_percentage}%` : "--";
  if (detectedCgpaEl) detectedCgpaEl.innerText = profile.detected_cgpa ? `${profile.detected_cgpa} / 10` : "Verified via Profile";

  // 2. Render Detected Skills Pills
  const skillsCloudEl = document.getElementById("resSkillsCloud");
  if (skillsCloudEl) {
    if (detectedSkills.length === 0) {
      skillsCloudEl.innerHTML = `<span style="color:var(--text-muted); font-size:0.8rem;">No recognized technical skills detected. Try adding explicit keywords like Python, SQL, Java, React, Docker.</span>`;
    } else {
      skillsCloudEl.innerHTML = detectedSkills.map(s => 
        `<span class="skill-pill skill-pill-detected"><i class="fa-solid fa-check"></i> ${escapeHtml(s)}</span>`
      ).join(" ");
    }
  }

  // 3. Render Match Cards Grid
  const gridEl = document.getElementById("resumeMatchesGrid");
  if (!gridEl) return;

  if (matches.length === 0) {
    gridEl.innerHTML = `<div style="grid-column: 1/-1; text-align:center; padding:2rem; color:var(--text-muted);">No published opportunities found in the catalog.</div>`;
    return;
  }

  gridEl.innerHTML = matches.map((m, idx) => {
    const isTop = idx === 0;
    const progressWidth = Math.min(100, Math.max(5, m.match_percentage));
    const matchedPills = (m.matched_skills || []).map(s => 
      `<span class="skill-pill skill-pill-matched"><i class="fa-solid fa-check"></i> ${escapeHtml(s)}</span>`
    ).join(" ") || `<span style="font-size:0.75rem; color:var(--text-muted);">None matched yet</span>`;

    const missingPills = (m.missing_skills || []).map(s => 
      `<span class="skill-pill skill-pill-missing"><i class="fa-solid fa-plus"></i> ${escapeHtml(s)}</span>`
    ).join(" ") || `<span style="font-size:0.75rem; color:#10b981;"><i class="fa-solid fa-check-double"></i> All skills covered!</span>`;

    const stipendDisplay = m.stipend_monthly > 0 ? `₹${Number(m.stipend_monthly).toLocaleString('en-IN')}/mo` : "Standard Placement Stipend";

    return `
      <div class="resume-match-card" style="${isTop ? 'border-color: #6366f1; box-shadow: 0 0 20px rgba(99,102,241,0.25);' : ''}">
        <div>
          <!-- Header: Company & Match Badge -->
          <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:0.5rem; margin-bottom:0.6rem;">
            <div>
              <div style="font-family:var(--font-heading); font-size:1.15rem; font-weight:700; color:#fff;">
                ${isTop ? '<i class="fa-solid fa-crown" style="color:#fbbf24; margin-right:4px;"></i>' : ''}
                ${escapeHtml(m.company_name)}
              </div>
              <div style="font-size:0.83rem; color:var(--primary-light); font-weight:600; margin-top:2px;">
                ${escapeHtml(m.title)}
              </div>
            </div>
            <div class="match-score-badge" style="background:${m.fit_color}22; color:${m.fit_color}; border:1px solid ${m.fit_color}55;">
              ${m.match_percentage}%
            </div>
          </div>

          <!-- Progress Bar -->
          <div class="match-progress-bar-container">
            <div class="match-progress-bar-fill" style="width:${progressWidth}%; background:${m.fit_color};"></div>
          </div>

          <!-- Location, Stipend, Vacancy Tags -->
          <div style="display:flex; flex-wrap:wrap; gap:0.5rem; font-size:0.76rem; color:var(--text-secondary); margin-bottom:0.85rem;">
            <span><i class="fa-solid fa-location-dot" style="color:#ec4899;"></i> ${escapeHtml(m.location)}</span>
            <span>•</span>
            <span style="color:#34d399; font-weight:600;"><i class="fa-solid fa-indian-rupee-sign"></i> ${stipendDisplay}</span>
            <span>•</span>
            <span><i class="fa-solid fa-users" style="color:#38bdf8;"></i> ${m.available_vacancies} Vacancies</span>
          </div>

          <!-- Skills Matched -->
          <div style="margin-bottom:0.65rem;">
            <div style="font-size:0.72rem; font-weight:700; color:#34d399; text-transform:uppercase; margin-bottom:3px;">
              <i class="fa-solid fa-circle-check"></i> Matched Skills (${(m.matched_skills || []).length})
            </div>
            <div>${matchedPills}</div>
          </div>

          <!-- Skills to Upskill / Missing -->
          <div style="margin-bottom:0.75rem;">
            <div style="font-size:0.72rem; font-weight:700; color:#fbbf24; text-transform:uppercase; margin-bottom:3px;">
              <i class="fa-solid fa-lightbulb"></i> Recommended to Learn / Upskill
            </div>
            <div>${missingPills}</div>
          </div>

          <!-- Rationale -->
          <div style="font-size:0.76rem; color:var(--text-muted); background:rgba(255,255,255,0.03); padding:0.5rem 0.65rem; border-radius:var(--radius-sm); border-left:3px solid ${m.fit_color}; margin-bottom:1rem;">
            ${escapeHtml(m.recommendation_reason)}
          </div>
        </div>

        <!-- 1-Click Action Button -->
        <div>
          <button class="btn btn-outline btn-sm" style="width:100%; border-color:#6366f1; color:#a5b4fc; font-weight:600; display:flex; align-items:center; justify-content:center; gap:6px;" 
                  onclick="selectCompanyAsPreference('${escapeJs(m.company_name)}', '${escapeJs(m.title)}', '${escapeJs(m.location)}')">
            <i class="fa-solid fa-bullseye"></i> Set as Preference 1 in Form
          </button>
        </div>
      </div>
    `;
  }).join("");
}

function selectCompanyAsPreference(company, role, location) {
  // Populate form fields in Internship Preference Form
  const pref1Company = document.getElementById("pref1Company");
  const pref1Role = document.getElementById("pref1Role");
  const pref1Loc = document.getElementById("pref1Location");

  if (pref1Company) pref1Company.value = company;
  if (pref1Role) pref1Role.value = role;
  if (pref1Loc) pref1Loc.value = location;

  // Switch to form view
  if (typeof switchView === "function") {
    switchView("form");
  }

  // Scroll to form inputs smoothly
  setTimeout(() => {
    if (pref1Company) {
      pref1Company.focus();
      pref1Company.style.outline = "2px solid #6366f1";
      setTimeout(() => { pref1Company.style.outline = "none"; }, 1500);
    }
  }, 200);

  alert(`✓ Set '${company}' (${role}) as your Preference 1 in the Internship Application Form!`);
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function escapeJs(str) {
  if (!str) return "";
  return String(str).replace(/'/g, "\\'").replace(/"/g, '\\"');
}

// Attach Drag & Drop Listeners on Document Ready
document.addEventListener("DOMContentLoaded", function() {
  const dropzone = document.getElementById("resumeDropzone");
  const fileInput = document.getElementById("resumeFileInput");

  if (dropzone && fileInput) {
    dropzone.addEventListener("click", () => fileInput.click());

    dropzone.addEventListener("dragover", (e) => {
      e.preventDefault();
      dropzone.classList.add("dragover");
    });

    dropzone.addEventListener("dragleave", () => {
      dropzone.classList.remove("dragover");
    });

    dropzone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropzone.classList.remove("dragover");
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        processSelectedResumeFile(e.dataTransfer.files[0]);
      }
    });
  }
});
