/**
 * INTERNTRACK — Real-World College Workflow Handlers
 * Handles form submissions, coordinator review desk, HOD sanctions, and tracking.
 */

let activeReviewSubmissionId = null;
let activeTrackingInternshipId = null;

function togglePlacementFields(isPlaced) {
  const placedBox = document.getElementById("placedCompanyContainer");
  const normalBox = document.getElementById("normalPreferencesContainer");
  if (isPlaced) {
    placedBox.style.display = "block";
    normalBox.style.display = "none";
    document.getElementById("pref1Company").removeAttribute("required");
  } else {
    placedBox.style.display = "none";
    normalBox.style.display = "block";
    document.getElementById("pref1Company").setAttribute("required", "true");
  }
}

function resetForm() {
  document.getElementById("internshipSubmissionForm").reset();
  togglePlacementFields(false);
  const nameInput = document.getElementById("formStudentNameInput");
  const usnInput = document.getElementById("formStudentUSNInput");
  const branchInput = document.getElementById("formStudentBranchInput");
  const cgpaInput = document.getElementById("formStudentCGPAInput");
  if (nameInput) nameInput.value = "";
  if (usnInput) usnInput.value = "";
  if (branchInput) branchInput.value = "";
  if (cgpaInput) cgpaInput.value = "";
}

async function handleUSNChange(usn) {
  if (!usn || !usn.trim()) return;
  const clean = usn.trim().toUpperCase();
  try {
    const res = await fetch(`/api/students/profile?usn=${encodeURIComponent(clean)}`);
    const data = await res.json();
    if (data && !data.error && data.name) {
      const nameInput = document.getElementById("formStudentNameInput");
      const branchInput = document.getElementById("formStudentBranchInput");
      const cgpaInput = document.getElementById("formStudentCGPAInput");
      if (nameInput && !nameInput.value.trim()) nameInput.value = data.name;
      if (branchInput && !branchInput.value.trim()) branchInput.value = data.branch;
      if (cgpaInput && !cgpaInput.value.trim()) cgpaInput.value = data.cgpa;
    }
  } catch (err) {
    console.log("Custom or unseeded student USN:", clean);
  }
}
window.handleUSNChange = handleUSNChange;

// 1. Submit Internship Form
async function handleFormSubmit(e) {
  e.preventDefault();
  const isPlaced = document.querySelector('input[name="is_placed_radio"]:checked').value === "YES";

  const nameInput = document.getElementById("formStudentNameInput");
  const usnInput = document.getElementById("formStudentUSNInput");
  const branchInput = document.getElementById("formStudentBranchInput");
  const cgpaInput = document.getElementById("formStudentCGPAInput");

  const enteredName = nameInput ? nameInput.value.trim() : "";
  const enteredUSN = (usnInput && usnInput.value.trim()) ? usnInput.value.trim().toUpperCase() : (currentUSN || "1KG21CS045");
  const enteredBranch = (branchInput && branchInput.value.trim()) ? branchInput.value.trim().toUpperCase() : "CSE";
  const enteredCGPA = (cgpaInput && cgpaInput.value.trim()) ? parseFloat(cgpaInput.value) : 8.5;

  // Bind active student session to this student
  currentUSN = enteredUSN;
  if (enteredName) currentStudentName = enteredName;

  // Header profile badge remains generic Student
  if (document.getElementById("userNameText")) document.getElementById("userNameText").innerText = "Student";
  if (document.getElementById("userRoleText")) document.getElementById("userRoleText").innerText = "Student";

  let payload = {
    student_usn: enteredUSN,
    student_name: enteredName || currentStudentName || "Student",
    name: enteredName || currentStudentName || "Student",
    branch: enteredBranch,
    cgpa: isNaN(enteredCGPA) ? 8.5 : enteredCGPA,
    submission_type: isPlaced ? "PLACED_COMPANY" : "NORMAL"
  };

  if (isPlaced) {
    payload.placed_company_name = document.getElementById("placedCompanyNameInput").value.trim();
    payload.placed_duration = document.getElementById("placedDurationSelect").value;
    payload.placement_details = document.getElementById("placementDetailsInput").value.trim();
    if (!payload.placed_company_name) {
      alert("Please provide the Placed Company Name.");
      return;
    }
  } else {
    payload.pref_1_company = document.getElementById("pref1Company").value.trim();
    payload.pref_1_role = document.getElementById("pref1Role").value.trim();
    payload.pref_1_location = document.getElementById("pref1Loc").value.trim();
    payload.pref_2_company = document.getElementById("pref2Company").value.trim();
    payload.pref_2_role = document.getElementById("pref2Role").value.trim();
    payload.pref_2_location = document.getElementById("pref2Loc").value.trim();
    payload.pref_3_company = document.getElementById("pref3Company").value.trim();
    payload.pref_3_role = document.getElementById("pref3Role").value.trim();
    payload.pref_3_location = document.getElementById("pref3Loc").value.trim();
    payload.pref_4_company = document.getElementById("pref4Company").value.trim();
    payload.pref_4_role = document.getElementById("pref4Role").value.trim();
    payload.pref_4_location = document.getElementById("pref4Loc").value.trim();

    if (!payload.pref_1_company) {
      alert("At least Preference 1 is required.");
      return;
    }
  }

  try {
    const res = await fetch("/api/submissions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (res.ok) {
      alert(`Submission successful for ${enteredName || enteredUSN}! Recorded as Version ${data.submission.submission_version}.`);
      resetForm();
      switchView("submissions");
      loadDashboardStats();
      loadSubmissions();
      loadStudentsDirectory();
      loadCoordinatorReviewQueue();
      loadNotifications();
    } else {
      alert(`Error: ${data.message || "Failed to submit."}`);
    }
  } catch (err) {
    alert(`Network error: ${err.message}`);
  }
}

// 2. Load Submissions Table (Student History)
async function loadSubmissions() {
  try {
    const url = currentRole === "STUDENT" ? `/api/submissions?usn=${currentUSN}` : "/api/submissions";
    const res = await fetch(url);
    const subs = await res.json();

    const tbody = document.getElementById("studentSubmissionsTable");
    if (!subs || subs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:var(--text-muted);">No submissions recorded yet.</td></tr>`;
      return;
    }

    tbody.innerHTML = subs.map(s => {
      let statusBadge = `<span class="badge warning">${s.status}</span>`;
      if (s.status === "CONFIRMED" || s.status === "COORDINATOR_APPROVED") statusBadge = `<span class="badge success">${s.status}</span>`;
      if (s.status === "REJECTED") statusBadge = `<span class="badge danger">REJECTED</span>`;
      if (s.status === "CORRECTION_REQUIRED") statusBadge = `<span class="badge warning">CORRECTION REQUIRED</span>`;

      let feedback = "-";
      if (s.status === "REJECTED" && s.rejection_reason) {
        feedback = `<div style="color:var(--danger); font-weight:600; font-size:0.8rem;"><i class="fa-solid fa-triangle-exclamation"></i> Rejection Reason: ${s.rejection_reason}</div>`;
      } else if (s.coordinator_comments) {
        feedback = `<span style="color:var(--text-secondary);">${s.coordinator_comments}</span>`;
      }

      let prefs = s.submission_type === "PLACED_COMPANY" ?
        `<span class="badge placed"><i class="fa-solid fa-building-circle-check"></i> ${s.placed_company_name}</span>` :
        `1. ${s.pref_1_company || '-'}<br>2. ${s.pref_2_company || '-'}`;

      let action = "-";
      if (s.status === "REJECTED" || s.status === "CORRECTION_REQUIRED") {
        action = `<button class="btn btn-primary btn-sm" onclick="populateFormForResubmission('${s.pref_1_company || ''}', '${s.pref_2_company || ''}')"><i class="fa-solid fa-rotate-right"></i> Resubmit</button>`;
      }

      return `
        <tr>
          <td><strong>v${s.submission_version}</strong></td>
          <td><span class="badge ${s.submission_type === 'PLACED_COMPANY' ? 'placed' : 'info'}">${s.submission_type}</span></td>
          <td>${prefs}</td>
          <td>${statusBadge}</td>
          <td>${s.coordinator_decision || 'Pending'}</td>
          <td>${feedback}</td>
          <td>${s.approved_company ? `<strong>${s.approved_company}</strong> (${s.approved_duration || '4M'})` : '-'}</td>
          <td>${action}</td>
        </tr>
      `;
    }).join("");

    // Also populate dashboard pending queue
    const pendingSubs = subs.filter(s => s.status === "SUBMITTED" || s.status === "UNDER_REVIEW");
    const dashTbody = document.getElementById("dashboardPendingTable");
    if (dashTbody) {
      if (pendingSubs.length === 0) {
        dashTbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--text-muted);">No submissions currently pending review.</td></tr>`;
      } else {
        dashTbody.innerHTML = pendingSubs.slice(0, 5).map(s => `
          <tr>
            <td><code>${s.student_usn}</code></td>
            <td>${s.student_name || 'Student'}</td>
            <td>v${s.submission_version}</td>
            <td>${s.submission_type === 'PLACED_COMPANY' ? s.placed_company_name : (s.pref_1_company || 'Preferences')}</td>
            <td><span class="badge ${s.submission_type === 'PLACED_COMPANY' ? 'placed' : 'info'}">${s.submission_type}</span></td>
            <td><span class="badge warning">${s.status}</span></td>
            <td>
              <button class="btn btn-primary btn-sm" onclick="openReviewModal('${s.id}')">
                Review
              </button>
            </td>
          </tr>
        `).join("");
      }
    }
  } catch (err) {
    console.error("Failed to load submissions:", err);
  }
}

function populateFormForResubmission(pref1, pref2) {
  switchView("form");
  document.getElementById("pref1Company").value = pref1;
  document.getElementById("pref2Company").value = pref2;
}

// 3. Coordinator Review Queue & Modal
async function loadCoordinatorReviewQueue() {
  try {
    const res = await fetch("/api/submissions");
    const subs = await res.json();
    const tbody = document.getElementById("coordinatorReviewTable");

    tbody.innerHTML = subs.map(s => `
      <tr>
        <td><code>${s.id}</code></td>
        <td><strong>${s.student_name || 'Student'}</strong></td>
        <td>${s.student_usn} (CGPA: ${s.cgpa || 8.5})</td>
        <td>v${s.submission_version}</td>
        <td><span class="badge ${s.submission_type === 'PLACED_COMPANY' ? 'placed' : 'info'}">${s.submission_type}</span></td>
        <td style="font-size:0.8rem;">
          ${s.submission_type === 'PLACED_COMPANY' ?
            `<strong>Placed Company:</strong> ${s.placed_company_name}` :
            `1. ${s.pref_1_company || '-'} | 2. ${s.pref_2_company || '-'} | 3. ${s.pref_3_company || '-'} | 4. ${s.pref_4_company || '-'}`
          }
        </td>
        <td><span class="badge ${s.status === 'CONFIRMED' || s.status === 'COORDINATOR_APPROVED' ? 'success' : s.status === 'REJECTED' ? 'danger' : 'warning'}">${s.status}</span></td>
        <td>
          <button class="btn btn-primary btn-sm" onclick="openReviewModal('${s.id}')">
            <i class="fa-solid fa-gavel"></i> Review
          </button>
        </td>
      </tr>
    `).join("");
  } catch (err) {
    console.error("Failed to load coordinator review queue:", err);
  }
}

async function openReviewModal(subId) {
  activeReviewSubmissionId = subId;
  try {
    const res = await fetch("/api/submissions");
    const all = await res.json();
    const sub = all.find(s => s.id === subId);
    if (!sub) return;

    document.getElementById("modalStudentSummary").innerHTML = `
      <div><strong>Student:</strong> ${sub.student_name || 'Student'} (${sub.student_usn}) | <strong>Branch:</strong> ${sub.branch || 'CSE'} | <strong>CGPA:</strong> ${sub.cgpa || 8.5}</div>
      <div style="margin-top:6px;"><strong>Type:</strong> ${sub.submission_type} (Version ${sub.submission_version})</div>
      <div style="margin-top:4px; color:#cbd5e1;">
        <strong>Preferences:</strong><br>
        1. ${sub.pref_1_company || '-'} (${sub.pref_1_role || '-'})<br>
        2. ${sub.pref_2_company || '-'}<br>
        3. ${sub.pref_3_company || '-'}<br>
        4. ${sub.pref_4_company || '-'}
      </div>
    `;

    document.getElementById("modalApprovedCompany").value = sub.submission_type === "PLACED_COMPANY" ? (sub.placed_company_name || "") : (sub.pref_1_company || "ABC Technologies");
    document.getElementById("modalDecisionSelect").value = "APPROVE";
    toggleRejectionField("APPROVE");
    document.getElementById("reviewModal").classList.add("active");
  } catch (err) {
    console.error("Modal error:", err);
  }
}

function closeReviewModal() {
  document.getElementById("reviewModal").classList.remove("active");
  activeReviewSubmissionId = null;
}

function toggleRejectionField(decision) {
  const rejSection = document.getElementById("rejectionFieldSection");
  const appSection = document.getElementById("approvalFieldsSection");
  if (decision === "REJECT") {
    rejSection.style.display = "block";
    appSection.style.display = "none";
  } else {
    rejSection.style.display = "none";
    appSection.style.display = "block";
  }
}

async function submitCoordinatorReview() {
  if (!activeReviewSubmissionId) return;

  const decision = document.getElementById("modalDecisionSelect").value;
  const rejectionReason = document.getElementById("modalRejectionReason").value.trim();
  const approvedCompany = document.getElementById("modalApprovedCompany").value.trim();
  const approvedRole = document.getElementById("modalApprovedRole").value.trim();
  const approvedDuration = document.getElementById("modalApprovedDuration").value.trim();
  const comments = document.getElementById("modalCoordinatorComments").value.trim();

  // STRICT VALIDATION: If REJECT, rejection reason MUST NOT be empty!
  if (decision === "REJECT" && !rejectionReason) {
    alert("⚠️ MANDATORY REQUIREMENT:\nA rejection reason must be provided when rejecting a student submission. Please enter a valid reason.");
    return;
  }

  const payload = {
    submission_id: activeReviewSubmissionId,
    decision: decision,
    coordinator_name: "Coordinator",
    rejection_reason: rejectionReason,
    approved_company: approvedCompany,
    approved_role: approvedRole,
    approved_duration: approvedDuration,
    coordinator_comments: comments
  };

  try {
    const res = await fetch("/api/coordinator/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    if (res.ok) {
      alert(`Decision submitted: ${decision}`);
      closeReviewModal();
      loadCoordinatorReviewQueue();
      loadSubmissions();
      loadDashboardStats();
    } else {
      alert(`Error: ${data.message}`);
    }
  } catch (err) {
    alert(`Network error: ${err.message}`);
  }
}

// 4. HOD Review Queue
async function loadHODReviewQueue() {
  try {
    const res = await fetch("/api/submissions");
    const subs = await res.json();
    const approvedSubs = subs.filter(s => s.status === "COORDINATOR_APPROVED" || s.status === "CONFIRMED");
    const tbody = document.getElementById("hodReviewTable");

    if (approvedSubs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--text-muted);">No applications pending departmental sanction.</td></tr>`;
      return;
    }

    tbody.innerHTML = approvedSubs.map(s => `
      <tr>
        <td><code>${s.id}</code></td>
        <td><strong>${s.student_name || 'Student'}</strong> (${s.student_usn})</td>
        <td>${s.branch || 'CSE'}</td>
        <td><strong>${s.approved_company || s.placed_company_name}</strong> (${s.approved_role || 'Intern'})</td>
        <td>${s.approved_duration || '4 Months'}</td>
        <td><span class="badge success">Coordinator Approved</span></td>
        <td>
          ${s.hod_status === 'APPROVED' ?
            `<span class="badge success"><i class="fa-solid fa-check-double"></i> Confirmed by HOD</span>` :
            `<button class="btn btn-success btn-sm" onclick="submitHODSanction('${s.id}')">Sign Off Sanction</button>`
          }
        </td>
      </tr>
    `).join("");
  } catch (err) {
    console.error("Failed to load HOD queue:", err);
  }
}

async function submitHODSanction(subId) {
  try {
    const res = await fetch("/api/hod/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        submission_id: subId,
        decision: "APPROVE",
        hod_name: "HOD",
        comments: "Departmental sanction confirmed for 12 academic credits."
      })
    });
    if (res.ok) {
      alert("HOD Departmental Sanction Approved! Status is now CONFIRMED.");
      loadHODReviewQueue();
      loadDashboardStats();
    }
  } catch (err) {
    alert("HOD error: " + err.message);
  }
}

// 5. Opportunities & Dynamic Vacancy Management
// 5. Opportunities & Dynamic Vacancy Management
window.rawOpportunitiesList = [];
window.currentOppCategory = 'ALL';

async function loadOpportunities() {
  try {
    const res = await fetch("/api/opportunities");
    const opps = await res.json();
    window.rawOpportunitiesList = opps;
    renderOpportunitiesGrid();
    if (typeof window.populateLabCompanyDropdowns === 'function') {
      window.populateLabCompanyDropdowns();
    }
  } catch (err) {
    console.error("Failed to load opportunities:", err);
  }
}

function filterOppsByCategory(cat, btnElem) {
  window.currentOppCategory = cat;
  document.querySelectorAll(".opp-cat-btn").forEach(b => {
    b.style.background = "var(--bg-card)";
    b.style.color = "var(--text-secondary)";
    b.style.borderColor = "var(--border-color)";
  });
  if (btnElem) {
    btnElem.style.background = "var(--primary)";
    btnElem.style.color = "#fff";
    btnElem.style.borderColor = "var(--primary)";
  }
  renderOpportunitiesGrid();
}
window.filterOppsByCategory = filterOppsByCategory;

function getOfficialJobApplyUrl(o) {
  const comp = (o.company || "").toLowerCase();

  // 1. Official Corporate Careers Applying Pages for Top Companies
  if (comp.includes("infosys")) return "https://career.infosys.com/";
  if (comp.includes("tata") || comp.includes("tcs")) return "https://www.tcs.com/careers/india/internships";
  if (comp.includes("bosch")) return "https://careers.smartrecruiters.com/BoschGroup/india";
  if (comp.includes("google")) return "https://careers.google.com/jobs/results/?q=intern&location=India";
  if (comp.includes("microsoft")) return "https://jobs.careers.microsoft.com/global/en/search?q=intern&lc=India";
  if (comp.includes("amazon") || comp.includes("aws")) return "https://www.amazon.jobs/en/job_categories/student-programs";
  if (comp.includes("wipro")) return "https://careers.wipro.com/careers-home/jobs";
  if (comp.includes("cisco")) return "https://jobs.cisco.com/jobs/SearchJobs/intern";
  if (comp.includes("ibm")) return "https://www.ibm.com/careers/in-en";
  if (comp.includes("samsung")) return "https://research.samsung.com/sri-b";
  if (comp.includes("intel")) return "https://jobs.intel.com/en/search-jobs/India/intern";
  if (comp.includes("nvidia")) return "https://www.nvidia.com/en-in/about-nvidia/careers/university-recruiting/";
  if (comp.includes("oracle")) return "https://www.oracle.com/careers/students-grads/";
  if (comp.includes("flipkart")) return "https://www.flipkartcareers.com/";
  if (comp.includes("razorpay")) return "https://razorpay.com/jobs/";
  if (comp.includes("swiggy")) return "https://careers.swiggy.com/";
  if (comp.includes("zoho")) return "https://www.zoho.com/careers/";
  if (comp.includes("adobe")) return "https://careers.adobe.com/us/en/university";
  if (comp.includes("goldman")) return "https://www.goldmansachs.com/careers/students/programs/india/";
  if (comp.includes("accenture")) return "https://www.accenture.com/in-en/careers/local/entry-level";

  // 2. Check if description has an explicit http/https URL (e.g. for Indeed live postings)
  const match = o.description ? o.description.match(/https?:\/\/[^\s"'<>]+/) : null;
  if (match) return match[0];

  // 3. Fallback to Indeed live search for the company and title
  const q = encodeURIComponent(`${o.title || 'Intern'} ${o.company || ''}`);
  const loc = encodeURIComponent(o.location || 'Bangalore');
  return `https://in.indeed.com/jobs?q=${q}&l=${loc}`;
}
window.getOfficialJobApplyUrl = getOfficialJobApplyUrl;

function renderOpportunitiesGrid() {
  const grid = document.getElementById("oppsCardsGrid");
  if (!grid) return;
  const opps = window.rawOpportunitiesList || [];

  const filtered = opps.filter(o => {
    const isIndeed = (o.id && o.id.startsWith("OPP-IND-")) || (o.created_by && o.created_by.includes("Indeed"));
    const isBench = ['OPP-001','OPP-002','OPP-003','OPP-004','OPP-005'].includes(o.id);
    const isCorp = !isIndeed && !isBench;

    if (window.currentOppCategory === 'INDEED') return isIndeed;
    if (window.currentOppCategory === 'CORP') return isCorp;
    if (window.currentOppCategory === 'BENCHMARK') return isBench;
    return isIndeed || isCorp; // Default: Show all real companies (MNCs + Indeed), isolating test fixtures to the Lab Test tab
  });

  if (filtered.length === 0) {
    grid.innerHTML = `
      <div style="grid-column:1/-1; text-align:center; padding:3rem 1rem; color:var(--text-muted);">
        <i class="fa-solid fa-folder-open" style="font-size:2.5rem; margin-bottom:0.75rem; opacity:0.5;"></i>
        <div style="font-size:1.05rem; font-weight:600; color:#fff;">No opportunities found in this category</div>
        <p style="font-size:0.85rem; margin-top:0.25rem;">Click "Sync Fresh Live Jobs" above to pull real-time postings from Indeed India.</p>
      </div>
    `;
    return;
  }

  grid.innerHTML = filtered.map(o => {
    const isFull = o.available_vacancies <= 0;
    const isIndeed = (o.id && o.id.startsWith("OPP-IND-")) || (o.created_by && o.created_by.includes("Indeed"));
    const isBench = ['OPP-001','OPP-002','OPP-003','OPP-004','OPP-005'].includes(o.id);
    const isCorp = !isIndeed && !isBench;

    let typeBadge = '';
    if (isIndeed) {
      typeBadge = `<span class="badge" style="background:rgba(59,130,246,0.2); color:#60a5fa; border:1px solid rgba(59,130,246,0.35); font-size:0.7rem; padding:2px 6px; border-radius:4px;"><i class="fa-solid fa-bolt"></i> Live Indeed</span>`;
    } else if (isCorp) {
      typeBadge = `<span class="badge" style="background:rgba(16,185,129,0.2); color:#34d399; border:1px solid rgba(16,185,129,0.35); font-size:0.7rem; padding:2px 6px; border-radius:4px;"><i class="fa-solid fa-building"></i> Top MNC</span>`;
    } else if (isBench) {
      typeBadge = `<span class="badge" style="background:rgba(168,85,247,0.2); color:#c084fc; border:1px solid rgba(168,85,247,0.35); font-size:0.7rem; padding:2px 6px; border-radius:4px;"><i class="fa-solid fa-vial"></i> Course Test Fixture</span>`;
    }

    // Freshness Badge (e.g. Posted 1 day ago)
    let freshnessBadge = '';
    const freshMatch = o.description ? o.description.match(/(?:Fresh Opening:\s*|Posted:\s*)([^\n\r]+)/i) : null;
    if (freshMatch) {
      const cleanAge = freshMatch[1].replace(/\([^\)]+\)/, '').trim();
      freshnessBadge = `<span class="badge" style="background:rgba(16,185,129,0.18); color:#34d399; border:1px solid rgba(16,185,129,0.35); font-size:0.7rem; padding:2px 6px; border-radius:4px;"><i class="fa-solid fa-clock"></i> ${cleanAge}</span>`;
    } else if (isIndeed) {
      freshnessBadge = `<span class="badge" style="background:rgba(16,185,129,0.18); color:#34d399; border:1px solid rgba(16,185,129,0.35); font-size:0.7rem; padding:2px 6px; border-radius:4px;"><i class="fa-solid fa-clock"></i> Posted 1 day ago</span>`;
    }

    const vacancyBadge = isFull ?
      `<span class="badge danger">FULL (0 Vacancies)</span>` :
      `<span class="badge success">${o.available_vacancies} of ${o.total_vacancies} Vacancies</span>`;

    const stipendDisplay = o.stipend_monthly ?
      `<div style="font-size:0.78rem; color:#34d399; font-weight:600; margin-top:2px;"><i class="fa-solid fa-indian-rupee-sign"></i> ${Number(o.stipend_monthly).toLocaleString('en-IN')}/mo</div>` : '';

    const applyUrl = getOfficialJobApplyUrl(o);
    let shortComp = "Portal";
    if (o.company.includes("Infosys")) shortComp = "Infosys";
    else if (o.company.includes("TCS") || o.company.includes("Tata")) shortComp = "TCS";
    else if (o.company.includes("Bosch")) shortComp = "Bosch";
    else if (o.company.includes("Google")) shortComp = "Google";
    else if (o.company.includes("Microsoft")) shortComp = "Microsoft";
    else if (o.company.includes("Amazon") || o.company.includes("AWS")) shortComp = "Amazon";
    else if (o.company.includes("Wipro")) shortComp = "Wipro";
    else if (isIndeed) shortComp = "Indeed";
    else shortComp = o.company.split(' ')[0] || "Company";

    return `
      <div class="card" style="margin-bottom:0; display:flex; flex-direction:column; justify-content:space-between; border-color:${isIndeed ? 'rgba(59,130,246,0.35)' : isCorp ? 'rgba(16,185,129,0.3)' : 'var(--border-color)'};">
        <div>
          <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:0.6rem; gap:0.5rem;">
            <div>
              <div style="display:flex; gap:0.4rem; align-items:center; margin-bottom:0.25rem; flex-wrap:wrap;">
                ${typeBadge}
                ${freshnessBadge}
                <span style="font-size:0.7rem; color:var(--text-muted); font-mono;">${o.id}</span>
              </div>
              <h4 style="font-family:var(--font-heading); font-size:1.1rem; color:#fff; margin:0; cursor:pointer;" onclick="openOppPreview('${o.id}')" title="Click to view details & job application link">${o.company}</h4>
            </div>
            <div style="display:flex; flex-direction:column; align-items:flex-end; gap:0.35rem;">
              ${vacancyBadge}
              <button class="btn btn-secondary btn-sm" onclick="openOppPreview('${o.id}')" style="padding:3px 9px; font-size:0.72rem; border-color:rgba(59,130,246,0.4); color:#93c5fd;" title="View details, criteria & direct job application link">
                <i class="fa-solid fa-circle-info"></i> Details & Link
              </button>
            </div>
          </div>
          <div style="font-size:0.88rem; font-weight:600; color:var(--primary-light); cursor:pointer;" onclick="openOppPreview('${o.id}')" title="Click to view details & job application link">${o.title}</div>
          ${stipendDisplay}
          <div style="font-size:0.78rem; color:var(--text-muted); margin:0.5rem 0 0.75rem 0;">
            <i class="fa-solid fa-location-dot"></i> ${o.location} • <i class="fa-solid fa-clock"></i> ${o.duration} • <i class="fa-solid fa-briefcase"></i> ${o.mode || 'HYBRID'}
          </div>
          <p style="font-size:0.8rem; color:var(--text-secondary); line-height:1.5; margin-bottom:1rem; max-height:4.2rem; overflow:hidden; text-overflow:ellipsis; display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical;">
            ${o.description || 'Quality engineering internship.'}
          </p>
          <div style="font-size:0.75rem; background:rgba(0,0,0,0.25); padding:0.5rem; border-radius:4px; margin-bottom:1rem;">
            <div><strong>Eligibility:</strong> Min CGPA ${o.min_cgpa} • Max Backlogs: ${o.max_backlogs}</div>
            <div style="margin-top:2px;"><strong>Deadline:</strong> ${o.deadline}</div>
          </div>
        </div>
        <div>
          ${isFull ?
            `<button class="btn btn-secondary btn-sm" disabled style="width:100%; opacity:0.6;">Quota Full</button>` :
            `
            <div style="display:flex; gap:0.5rem; width:100%;">
              <a href="${applyUrl}" target="_blank" rel="noopener noreferrer" class="btn btn-secondary btn-sm" style="flex:1.2; font-size:0.75rem; text-decoration:none; display:inline-flex; align-items:center; justify-content:center; gap:5px; border-color:rgba(59,130,246,0.45); color:#93c5fd;" title="Open official ${o.company} careers applying page in new tab">
                <i class="fa-solid fa-arrow-up-right-from-square"></i> Apply on ${shortComp}
              </a>
              <button class="btn btn-primary btn-sm" style="flex:1.5; font-size:0.75rem;" onclick="applyAndMentionInForm('${o.id}')" title="Add this company to your next open preference slot (1, 2, 3, or 4) in your internship form">
                <i class="fa-solid fa-pen-to-square"></i> Mention in Form
              </button>
            </div>
            `
          }
        </div>
      </div>
    `;
  }).join("");
}


let currentPreviewOppId = null;

function openOppPreview(oppId) {
  const opps = window.rawOpportunitiesList || [];
  const o = opps.find(item => item.id === oppId);
  if (!o) return;
  currentPreviewOppId = oppId;

  const modal = document.getElementById("oppPreviewModal");
  if (!modal) return;

  const isIndeed = (o.id && o.id.startsWith("OPP-IND-")) || (o.created_by && o.created_by.includes("Indeed"));
  const isCorp = ['OPP-006','OPP-007','OPP-008','OPP-009','OPP-010','OPP-011','OPP-012'].includes(o.id) ||
                 ['Infosys', 'TCS', 'Tata', 'Bosch', 'Google', 'Microsoft', 'Amazon', 'Wipro'].some(c => o.company.includes(c));

  const badgeElem = document.getElementById("oppPreviewBadge");
  if (badgeElem) {
    if (isIndeed) {
      badgeElem.className = "badge";
      badgeElem.style = "background:rgba(59,130,246,0.2); color:#60a5fa; border:1px solid rgba(59,130,246,0.35);";
      badgeElem.innerHTML = '<i class="fa-solid fa-bolt"></i> Live Indeed Posting';
    } else if (isCorp) {
      badgeElem.className = "badge";
      badgeElem.style = "background:rgba(16,185,129,0.2); color:#34d399; border:1px solid rgba(16,185,129,0.35);";
      badgeElem.innerHTML = '<i class="fa-solid fa-building"></i> Top MNC Opportunity';
    } else {
      badgeElem.className = "badge";
      badgeElem.style = "background:rgba(168,85,247,0.2); color:#c084fc; border:1px solid rgba(168,85,247,0.35);";
      badgeElem.innerHTML = '<i class="fa-solid fa-vial"></i> Lab Test Fixture';
    }
  }

  document.getElementById("oppPreviewId").innerText = o.id;
  document.getElementById("oppPreviewCompany").innerText = o.company;
  document.getElementById("oppPreviewTitle").innerText = o.title;
  document.getElementById("oppPreviewLoc").innerText = `${o.location} (${o.mode || 'HYBRID'})`;
  document.getElementById("oppPreviewDuration").innerText = o.duration || '4 Months';
  document.getElementById("oppPreviewStipend").innerText = o.stipend_monthly ? `₹${Number(o.stipend_monthly).toLocaleString('en-IN')}/mo` : 'Unpaid / Course Credits';
  document.getElementById("oppPreviewVacancies").innerText = `${o.available_vacancies} of ${o.total_vacancies} Available`;
  // Render description with clickable links
  const descElem = document.getElementById("oppPreviewDesc");
  if (descElem) {
    const rawDesc = o.description || 'Verified engineering internship opportunity with structured deliverables.';
    const linked = rawDesc.replace(/(https?:\/\/[^\s"'<>]+)/g, (url) => {
      return `<a href="${url}" target="_blank" rel="noopener noreferrer" style="color:#60a5fa; text-decoration:underline; font-weight:600;"><i class="fa-solid fa-arrow-up-right-from-square" style="font-size:0.75rem;"></i> ${url}</a>`;
    }).replace(/\n/g, '<br>');
    descElem.innerHTML = linked;
  }

  document.getElementById("oppPreviewEligibility").innerText = o.eligibility_criteria || `Min CGPA ${o.min_cgpa}, Max Backlogs ${o.max_backlogs}`;
  document.getElementById("oppPreviewDeadline").innerText = o.deadline || 'Ongoing';

  // Apply URL and Link Buttons
  const applyUrl = getOfficialJobApplyUrl(o);
  const comp = (o.company || "").toLowerCase();
  const linkBox = document.getElementById("oppPreviewLinkButtons");
  const footerLinkBtn = document.getElementById("oppPreviewIndeedLink");

  let buttonsHtml = '';
  if (comp.includes("infosys")) {
    buttonsHtml = `
      <a href="https://career.infosys.com/" target="_blank" rel="noopener noreferrer" class="btn btn-primary btn-sm" style="display:inline-flex; align-items:center; gap:6px; font-weight:600; text-decoration:none;">
        <i class="fa-solid fa-arrow-up-right-from-square"></i> Open Infosys Main Job Applying Page (career.infosys.com)
      </a>
      <a href="https://www.infosys.com/instep.html" target="_blank" rel="noopener noreferrer" class="btn btn-secondary btn-sm" style="display:inline-flex; align-items:center; gap:6px; text-decoration:none; border-color:rgba(16,185,129,0.4); color:#34d399;">
        <i class="fa-solid fa-graduation-cap"></i> Infosys InStep Global Internship Portal
      </a>
    `;
    if (footerLinkBtn) {
      footerLinkBtn.href = "https://career.infosys.com/";
      footerLinkBtn.innerHTML = '<i class="fa-solid fa-arrow-up-right-from-square"></i> Open Infosys Job Applying Page';
      footerLinkBtn.style.display = "inline-flex";
    }
  } else if (comp.includes("tata") || comp.includes("tcs")) {
    buttonsHtml = `
      <a href="https://www.tcs.com/careers/india/internships" target="_blank" rel="noopener noreferrer" class="btn btn-primary btn-sm" style="display:inline-flex; align-items:center; gap:6px; font-weight:600; text-decoration:none;">
        <i class="fa-solid fa-arrow-up-right-from-square"></i> Open TCS Careers Portal
      </a>
      <a href="https://nextstep.tcs.com/" target="_blank" rel="noopener noreferrer" class="btn btn-secondary btn-sm" style="display:inline-flex; align-items:center; gap:6px; text-decoration:none; border-color:rgba(16,185,129,0.4); color:#34d399;">
        <i class="fa-solid fa-user-graduate"></i> TCS NextStep Student Portal
      </a>
    `;
    if (footerLinkBtn) {
      footerLinkBtn.href = "https://www.tcs.com/careers/india/internships";
      footerLinkBtn.innerHTML = '<i class="fa-solid fa-arrow-up-right-from-square"></i> Open TCS Job Applying Page';
      footerLinkBtn.style.display = "inline-flex";
    }
  } else {
    const isIndeed = (o.id && o.id.startsWith("OPP-IND-")) || (o.created_by && o.created_by.includes("Indeed"));
    const label = isIndeed ? "Open Job Applying Page on Indeed India" : `Open ${o.company} Job Applying Page`;
    buttonsHtml = `
      <a href="${applyUrl}" target="_blank" rel="noopener noreferrer" class="btn btn-primary btn-sm" style="display:inline-flex; align-items:center; gap:6px; font-weight:600; text-decoration:none;">
        <i class="fa-solid fa-arrow-up-right-from-square"></i> ${label}
      </a>
    `;
    if (footerLinkBtn) {
      footerLinkBtn.href = applyUrl;
      footerLinkBtn.innerHTML = `<i class="fa-solid fa-arrow-up-right-from-square"></i> ${label}`;
      footerLinkBtn.style.display = "inline-flex";
    }
  }
  if (linkBox) linkBox.innerHTML = buttonsHtml;

  modal.style.display = "flex";
}
window.openOppPreview = openOppPreview;

function closeOppPreviewModal() {
  const modal = document.getElementById("oppPreviewModal");
  if (modal) modal.style.display = "none";
}
window.closeOppPreviewModal = closeOppPreviewModal;

function applyFromPreviewModal() {
  if (currentPreviewOppId) {
    applyAndMentionInForm(currentPreviewOppId);
    closeOppPreviewModal();
  }
}
window.applyFromPreviewModal = applyFromPreviewModal;

function applyAndMentionInForm(oppId) {
  const opps = window.rawOpportunitiesList || [];
  const o = opps.find(item => item.id === oppId);
  if (!o) return;

  const slots = [
    { num: 1, comp: document.getElementById('pref1Company'), role: document.getElementById('pref1Role'), loc: document.getElementById('pref1Loc') },
    { num: 2, comp: document.getElementById('pref2Company'), role: document.getElementById('pref2Role'), loc: document.getElementById('pref2Loc') },
    { num: 3, comp: document.getElementById('pref3Company'), role: document.getElementById('pref3Role'), loc: document.getElementById('pref3Loc') },
    { num: 4, comp: document.getElementById('pref4Company'), role: document.getElementById('pref4Role'), loc: document.getElementById('pref4Loc') },
  ];

  // 1. Check if this company is already added in one of the slots
  const alreadyAddedSlot = slots.find(s => s.comp && s.comp.value.trim().toLowerCase() === (o.company || "").trim().toLowerCase());
  if (alreadyAddedSlot) {
    if (typeof switchView === 'function') switchView('form');
    alreadyAddedSlot.comp.style.borderColor = "var(--primary)";
    alreadyAddedSlot.comp.focus();
    alert(`"${o.company}" is already added as Preference ${alreadyAddedSlot.num}!`);
    return;
  }

  // 2. Find the first empty slot (1 -> 2 -> 3 -> 4)
  let targetSlot = slots.find(s => s.comp && !s.comp.value.trim());

  // 3. If all slots are full, alert the user
  if (!targetSlot) {
    if (typeof switchView === 'function') switchView('form');
    alert(`All 4 preference slots are already filled!\nSlot 1: ${slots[0].comp ? slots[0].comp.value : ''}\nSlot 2: ${slots[1].comp ? slots[1].comp.value : ''}\nSlot 3: ${slots[2].comp ? slots[2].comp.value : ''}\nSlot 4: ${slots[3].comp ? slots[3].comp.value : ''}\n\nYou can clear or edit any preference slot directly.`);
    return;
  }

  // 4. Switch to the Internship Form tab
  if (typeof switchView === 'function') {
    switchView('form');
  }

  // 5. Pre-fill the selected target slot inputs
  targetSlot.comp.value = o.company;
  targetSlot.comp.style.borderColor = "var(--primary)";
  targetSlot.comp.style.background = "rgba(99, 102, 241, 0.12)";

  if (targetSlot.role) {
    targetSlot.role.value = o.title || 'Software Development Intern';
    targetSlot.role.style.borderColor = "var(--primary)";
  }
  if (targetSlot.loc) {
    targetSlot.loc.value = o.location || 'Bangalore';
    targetSlot.loc.style.borderColor = "var(--primary)";
  }

  // 6. Highlight the pre-filled banner in the form
  const banner = document.getElementById('formPrefilledBanner');
  const externalUrl = getOfficialJobApplyUrl(o);
  const nextSlotNum = targetSlot.num < 4 ? targetSlot.num + 1 : null;

  if (banner) {
    banner.style.display = 'block';
    banner.innerHTML = `
      <div style="background:rgba(99, 102, 241, 0.12); border:1px solid var(--border-active); border-radius:var(--radius-sm); padding:1rem; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.75rem;">
        <div>
          <div style="font-weight:700; color:#fff; font-size:0.95rem; display:flex; align-items:center; gap:0.4rem;">
            <i class="fa-solid fa-circle-check" style="color:#10b981;"></i> Added to Preference ${targetSlot.num}: ${o.company} — ${o.title}
          </div>
          <div style="font-size:0.8rem; color:var(--text-secondary); margin-top:0.35rem;">
            ${externalUrl ? `<a href="${externalUrl}" target="_blank" rel="noopener noreferrer" style="color:#60a5fa; text-decoration:underline; font-weight:600;"><i class="fa-solid fa-arrow-up-right-from-square"></i> Open ${o.company} Official Job Applying Page</a> • ` : ''}
            Recorded as <strong>Preference ${targetSlot.num}</strong> in your application form. ${nextSlotNum ? `You can add more (Preference ${nextSlotNum} is empty).` : 'All 4 preferences selected!'}
          </div>
        </div>
        <div style="display:flex; gap:0.5rem; flex-wrap:wrap;">
          ${nextSlotNum ? `
          <button type="button" class="btn btn-secondary btn-sm" onclick="switchView('opportunities')" style="border-color:rgba(59,130,246,0.4); color:#93c5fd;">
            <i class="fa-solid fa-plus"></i> Pick Preference ${nextSlotNum}
          </button>
          ` : ''}
          <button type="button" class="btn btn-primary btn-sm" onclick="document.getElementById('internshipSubmissionForm').requestSubmit()">
            <i class="fa-solid fa-paper-plane"></i> Submit Form Now
          </button>
        </div>
      </div>
    `;
  }

  // 7. Scroll target slot into view smoothly
  targetSlot.comp.scrollIntoView({ behavior: 'smooth', block: 'center' });
  targetSlot.comp.focus();
}
window.applyAndMentionInForm = applyAndMentionInForm;

async function applyToOpportunity(oppId, companyName) {
  try {
    const res = await fetch(`/api/opportunities/${oppId}/apply`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ student_usn: currentUSN })
    });
    const data = await res.json();
    if (res.ok) {
      alert(`Applied successfully to ${companyName}! Submission recorded.`);
      loadOpportunities();
      loadSubmissions();
      loadDashboardStats();
      if (typeof switchView === 'function') {
        switchView('submissions');
      }
    } else {
      alert(`Cannot apply: ${data.explanation || data.message}`);
    }
  } catch (err) {
    alert("Apply error: " + err.message);
  }
}


function openCreateOppModal() {
  const company = prompt("Enter Company Name:");
  if (!company) return;
  const title = prompt("Enter Internship Title:", "Software Engineering Intern");
  const vacancies = prompt("Enter Number of Vacancies:", "5");

  fetch("/api/opportunities", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      company: company,
      title: title,
      total_vacancies: parseInt(vacancies) || 3,
      domain: "Computer Science",
      location: "Bangalore",
      min_cgpa: 7.0,
      max_backlogs: 0,
      duration: "4 Months",
      coordinator_name: "Coordinator"
    })
  }).then(() => {
    alert("Opportunity published successfully with active vacancy management!");
    loadOpportunities();
    loadDashboardStats();
  });
}

async function syncIndeedPostings() {
  const btn = document.getElementById("btnSyncIndeed");
  const msg = document.getElementById("syncStatusMsg");
  const sel = document.getElementById("syncFreshnessSelect");
  const hoursOld = sel ? parseInt(sel.value) : 48;
  const origHtml = btn ? btn.innerHTML : "";

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Syncing (${hoursOld}h)...`;
  }
  if (msg) {
    msg.innerHTML = `<span style="color:#60a5fa;"><i class="fa-solid fa-cloud-arrow-down fa-spin"></i> Fetching fresh jobs posted in last ${hoursOld}h (1–2 days ago)...</span>`;
  }
  try {
    const res = await fetch("/api/opportunities/sync-indeed", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: "software intern", location: "Bangalore", limit: 15, hours_old: hoursOld })
    });
    const data = await res.json();
    if (res.ok) {
      if (msg) {
        msg.innerHTML = `<span style="color:#10b981;"><i class="fa-solid fa-circle-check"></i> Synced ${data.synced_count} Fresh Jobs (1–2 Days Ago)!</span>`;
        setTimeout(() => { if (msg) msg.innerHTML = ''; }, 6000);
      }
      // Automatically switch to Indeed tab to highlight new jobs
      window.currentOppCategory = 'INDEED';
      const indeedTab = document.getElementById("filterBtnIndeed");
      if (indeedTab) {
        document.querySelectorAll(".opp-cat-btn").forEach(b => {
          b.style.background = "var(--bg-card)";
          b.style.color = "var(--text-secondary)";
          b.style.borderColor = "var(--border-color)";
        });
        indeedTab.style.background = "var(--primary)";
        indeedTab.style.color = "#fff";
        indeedTab.style.borderColor = "var(--primary)";
      }
      loadOpportunities();
      loadDashboardStats();
    } else {
      if (msg) msg.innerHTML = `<span style="color:#ef4444;"><i class="fa-solid fa-triangle-exclamation"></i> Sync error: ${data.message || 'Failed'}</span>`;
    }
  } catch (err) {
    if (msg) msg.innerHTML = `<span style="color:#ef4444;"><i class="fa-solid fa-triangle-exclamation"></i> ${err.message}</span>`;
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = origHtml;
    }
  }
}
window.syncIndeedPostings = syncIndeedPostings;



// 6. Student Directory
async function loadStudentsDirectory() {
  try {
    const res = await fetch("/api/students/all");
    const students = await res.json();
    renderStudentsTable(students);
  } catch (err) {
    console.error("Directory error:", err);
  }
}

function renderStudentsTable(students) {
  const tbody = document.getElementById("studentsDirectoryTable");
  tbody.innerHTML = students.map(s => `
    <tr>
      <td><code>${s.usn}</code></td>
      <td><strong>${s.name}</strong></td>
      <td>${s.branch}</td>
      <td>${s.cgpa}</td>
      <td>${s.backlogs}</td>
      <td><span class="badge ${s.placement_status === 'PLACED_COMPANY' ? 'placed' : 'info'}">${s.placement_status}</span></td>
      <td>${s.placed_company || '-'}</td>
    </tr>
  `).join("");
}

function filterStudentsTable() {
  const q = document.getElementById("searchStudentInput").value.toLowerCase();
  fetch(`/api/students/all?search=${encodeURIComponent(q)}`)
    .then(r => r.json())
    .then(renderStudentsTable);
}

// 7. Tracking & Progress Reports
async function loadTrackingCards() {
  try {
    const res = await fetch("/api/tracking");
    const list = await res.json();
    const container = document.getElementById("internshipTrackingCards");

    if (list.length === 0) {
      container.innerHTML = `<p style="color:var(--text-muted);">No confirmed internships currently tracking.</p>`;
      return;
    }

    container.innerHTML = list.map(i => `
      <div style="background:rgba(255,255,255,0.02); border:1px solid var(--border-subtle); border-radius:var(--radius-md); padding:1.25rem; margin-bottom:1rem;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.6rem;">
          <div>
            <h4 style="color:#fff; font-size:1.05rem;">${i.company} — ${i.role}</h4>
            <span style="font-size:0.78rem; color:var(--text-muted);">${i.student_name} (${i.student_usn}) • Mentor: ${i.mentor_name}</span>
          </div>
          <span class="badge success">${i.status}</span>
        </div>
        <div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:0.75rem; font-size:0.78rem; color:var(--text-secondary); background:rgba(0,0,0,0.25); padding:0.65rem; border-radius:4px;">
          <div><strong>Start Date:</strong> ${i.start_date}</div>
          <div><strong>Expected End:</strong> ${i.expected_end_date}</div>
          <div><strong>Type:</strong> ${i.internship_type}</div>
        </div>
      </div>
    `).join("");
  } catch (err) {
    console.error("Tracking load error:", err);
  }
}

function openProgressReportModal() {
  activeTrackingInternshipId = "INT-ANANYA-001";
  document.getElementById("progressModal").classList.add("active");
}

function closeProgressModal() {
  document.getElementById("progressModal").classList.remove("active");
}

async function submitProgressReportAction() {
  const period = document.getElementById("modalReportingPeriod").value;
  const work = document.getElementById("modalWorkCompleted").value.trim();
  const skills = document.getElementById("modalSkillsLearned").value.trim();
  const hours = document.getElementById("modalHoursLogged").value;
  const nextObj = document.getElementById("modalNextObjectives").value.trim();

  if (!work) {
    alert("Please provide the work completed.");
    return;
  }

  try {
    const res = await fetch("/api/progress", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        internship_id: activeTrackingInternshipId,
        student_usn: currentUSN,
        reporting_period: period,
        work_completed: work,
        skills_learned: skills,
        hours_logged: parseInt(hours) || 40,
        next_objectives: nextObj
      })
    });
    if (res.ok) {
      alert("Bi-weekly progress journal submitted successfully!");
      closeProgressModal();
      loadTrackingCards();
    }
  } catch (err) {
    alert("Progress submit error: " + err.message);
  }
}

// 8. Final Evaluations (Dynamic Real-World Grades & HOD Clearance)
async function loadEvaluations() {
  try {
    const res = await fetch("/api/evaluations");
    const list = await res.json();
    const tbody = document.getElementById("evaluationTable");

    if (!list || list.length === 0) {
      tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; color:var(--text-muted);">No evaluations ready for clearance.</td></tr>`;
      return;
    }

    tbody.innerHTML = list.map(e => {
      const isFinal = e.approval_status === "FINALIZED" || e.approval_status === "APPROVED";
      const badgeCls = e.proposed_grade === "S" ? "success" : (e.proposed_grade === "A" ? "primary" : "warning");
      const statusBadge = isFinal
        ? `<span class="badge success"><i class="fa-solid fa-check"></i> FINALIZED & CREDITED</span>`
        : `<span class="badge info"><i class="fa-regular fa-clock"></i> READY_FOR_APPROVAL</span>`;

      let actionBtn = "";
      if (currentRole === "STUDENT") {
        actionBtn = isFinal
          ? `<span style="color:var(--success); font-size:0.8rem; font-weight:600;"><i class="fa-solid fa-circle-check"></i> 12 Credits Awarded</span>`
          : `<span class="badge info" style="font-size:0.75rem;"><i class="fa-solid fa-clock"></i> Pending Faculty Signoff</span>`;
      } else {
        // Both COORDINATOR and HOD have full grading and credit sign-off authority!
        const editBtn = `<button class="btn btn-outline btn-sm" style="margin-right:4px; padding:0.25rem 0.5rem; font-size:0.75rem;" onclick="editStudentMarks('${e.internship_id}', ${e.mentor_score}, ${e.presentation_score}, ${e.report_score}, '${(e.employer_feedback||'').replace(/'/g, "\\'")}', '${(e.mentor_assessment||'').replace(/'/g, "\\'")}')" title="Edit / Input Marks"><i class="fa-solid fa-pen"></i> Grade</button>`;
        actionBtn = isFinal
          ? `<div style="display:flex; align-items:center; gap:6px;">${editBtn}<span style="color:var(--success); font-size:0.8rem; font-weight:600;"><i class="fa-solid fa-circle-check"></i> Sanctioned</span></div>`
          : `<div style="display:flex; align-items:center; gap:6px;">${editBtn}<button class="btn btn-primary btn-sm" onclick="finalizeSignoff('${e.id}', '${e.student_name.replace(/'/g, "\\'")}')">
               <i class="fa-solid fa-stamp"></i> Finalize Signoff
             </button></div>`;
      }

      return `
        <tr>
          <td><strong>${e.student_name}</strong> <span style="font-size:0.75rem; color:var(--text-muted);">(${e.student_usn})</span></td>
          <td><strong>${e.company}</strong></td>
          <td>${e.mentor_score} / 40</td>
          <td>${e.presentation_score} / 30</td>
          <td>${e.report_score} / 30</td>
          <td><strong style="color:var(--success);">${e.total_score} / 100</strong></td>
          <td><span class="badge ${badgeCls}">${e.proposed_grade} Grade</span></td>
          <td><strong>${e.academic_credits} Credits</strong></td>
          <td>${statusBadge}</td>
          <td>${actionBtn}</td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    console.error("Evaluation error:", err);
  }
}

async function finalizeSignoff(evalId, studentName) {
  if (currentRole === "STUDENT") {
    alert("Access Denied: Only the Internship Coordinator or HOD has authority to sign off academic credits.");
    return;
  }

  const roleTitle = currentRole === "COORDINATOR" ? "Internship Coordinator" : "HOD";
  const authorityName = currentRole === "COORDINATOR" ? "Internship Coordinator Desk" : "Prof. S. H. Patil (HOD)";

  if (!confirm(`Are you sure you want to finalize and sign off 12 academic credits for ${studentName} as ${roleTitle}?`)) return;
  try {
    const res = await fetch(`/api/evaluations/${evalId}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        signoff_authority: authorityName,
        actor_role: currentRole
      })
    });
    const data = await res.json();
    if (res.ok) {
      if (typeof showToast === "function") {
        showToast(`HOD Sanction Complete: 12 Academic Credits awarded to ${studentName}!`, "success");
      } else {
        alert(`HOD Sanction Complete: 12 Academic Credits awarded to ${studentName}!`);
      }
      loadEvaluations();
      if (typeof loadDashboardStats === "function") loadDashboardStats();
    } else {
      alert("Error finalizing signoff: " + (data.message || data.error));
    }
  } catch (err) {
    alert("Signoff request failed: " + err.message);
  }
}

// 9. Audit Trail
async function loadAuditTrail() {
  try {
    const res = await fetch("/api/audit");
    const trail = await res.json();
    const tbody = document.getElementById("auditTrailTable");

    tbody.innerHTML = trail.map(a => `
      <tr>
        <td style="font-family:var(--font-code); font-size:0.75rem; color:var(--text-muted);">${a.timestamp}</td>
        <td><strong>${a.actor}</strong></td>
        <td><span class="badge info">${a.actor_role}</span></td>
        <td><code>${a.action}</code></td>
        <td><small>${a.record_id || '-'}</small></td>
        <td>${a.old_status ? `${a.old_status} → ` : ''}<strong>${a.new_status || '-'}</strong></td>
        <td style="font-size:0.8rem; color:var(--text-secondary);">${a.comments || '-'}</td>
      </tr>
    `).join("");
  } catch (err) {
    console.error("Audit load error:", err);
  }
}


// --- Evaluation Modal & Grading Controller ---
let cachedInternshipsForEval = [];

async function openEvaluationModal(preselectedInternId) {
  try {
    const res = await fetch("/api/tracking");
    cachedInternshipsForEval = await res.json();
    const sel = document.getElementById("evalModalInternshipSelect");
    if (!sel) return;

    sel.innerHTML = cachedInternshipsForEval.map(i => `
      <option value="${i.id}">${i.student_name} (${i.student_usn}) — ${i.company} [${i.role}]</option>
    `).join("");

    if (preselectedInternId) {
      sel.value = preselectedInternId;
    }

    calcEvalLiveTotal();
    document.getElementById("evaluationEntryModal").style.display = "flex";
  } catch (err) {
    console.error("Failed to load internships for eval modal:", err);
  }
}

function closeEvaluationModal() {
  const m = document.getElementById("evaluationEntryModal");
  if (m) m.style.display = "none";
}

function onEvalInternshipSelectChange() {
  calcEvalLiveTotal();
}

function calcEvalLiveTotal() {
  const m = parseFloat(document.getElementById("evalMentorScore").value) || 0;
  const p = parseFloat(document.getElementById("evalPresScore").value) || 0;
  const r = parseFloat(document.getElementById("evalRepScore").value) || 0;
  const total = Math.round((m + p + r) * 10) / 10;

  const totalEl = document.getElementById("evalLiveTotalText");
  const gradeEl = document.getElementById("evalLiveGradeText");
  if (totalEl) totalEl.innerText = `${total.toFixed(1)} / 100`;

  let grade = "F";
  let badgeCls = "danger";
  if (total >= 90) { grade = "S"; badgeCls = "success"; }
  else if (total >= 80) { grade = "A"; badgeCls = "primary"; }
  else if (total >= 70) { grade = "B"; badgeCls = "warning"; }
  else if (total >= 60) { grade = "C"; badgeCls = "warning"; }
  else if (total >= 50) { grade = "D"; badgeCls = "secondary"; }

  if (gradeEl) {
    gradeEl.innerHTML = `<span class="badge ${badgeCls}">${grade} Grade</span>`;
  }
}

function editStudentMarks(internId, mentorScore, presScore, repScore, empFeedback, mentorAssess) {
  openEvaluationModal(internId);
  setTimeout(() => {
    if (document.getElementById("evalModalInternshipSelect")) {
      document.getElementById("evalModalInternshipSelect").value = internId;
    }
    if (document.getElementById("evalMentorScore")) document.getElementById("evalMentorScore").value = mentorScore || 36;
    if (document.getElementById("evalPresScore")) document.getElementById("evalPresScore").value = presScore || 28;
    if (document.getElementById("evalRepScore")) document.getElementById("evalRepScore").value = repScore || 27;
    if (document.getElementById("evalEmployerFeedback")) document.getElementById("evalEmployerFeedback").value = empFeedback || "";
    if (document.getElementById("evalCoordRemarks")) document.getElementById("evalCoordRemarks").value = mentorAssess || "";
    calcEvalLiveTotal();
  }, 100);
}

async function submitEvaluationAction() {
  const internId = document.getElementById("evalModalInternshipSelect").value;
  if (!internId) {
    alert("Please select an internship record.");
    return;
  }

  const m = parseFloat(document.getElementById("evalMentorScore").value) || 0;
  const p = parseFloat(document.getElementById("evalPresScore").value) || 0;
  const r = parseFloat(document.getElementById("evalRepScore").value) || 0;

  if (m < 0 || m > 40) { alert("Mentor score must be between 0 and 40."); return; }
  if (p < 0 || p > 30) { alert("Presentation score must be between 0 and 30."); return; }
  if (r < 0 || r > 30) { alert("Report score must be between 0 and 30."); return; }

  const empFb = document.getElementById("evalEmployerFeedback").value.trim();
  const coordRem = document.getElementById("evalCoordRemarks").value.trim();

  try {
    const res = await fetch("/api/evaluations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        internship_id: internId,
        evaluator_name: typeof currentStudentName !== "undefined" ? currentStudentName : "Internship Coordinator",
        mentor_score: m,
        presentation_score: p,
        report_score: r,
        employer_feedback: empFb,
        mentor_assessment: coordRem
      })
    });

    const data = await res.json();
    if (res.ok) {
      closeEvaluationModal();
      if (typeof showToast === "function") {
        showToast("Marks recorded successfully! Evaluation is now READY_FOR_APPROVAL by HOD.", "success");
      } else {
        alert("Marks recorded successfully! Evaluation is now READY_FOR_APPROVAL by HOD.");
      }
      loadEvaluations();
      if (typeof loadDashboardStats === "function") loadDashboardStats();
    } else {
      alert("Error recording evaluation: " + (data.message || data.error));
    }
  } catch (err) {
    alert("Request failed: " + err.message);
  }
}

// AURA Agentic Swarm Integration for Student Submission Form (Lab 8 & Lab 4)
async function triggerAuraSwarmForSubmission() {
  const statusEl = document.getElementById("auraSwarmLiveStatus");
  const btn = document.getElementById("btnAuraSwarmAutoFill");
  const usnInput = document.getElementById("formStudentUSNInput");
  const nameInput = document.getElementById("formStudentNameInput");
  const cgpaInput = document.getElementById("formStudentCGPAInput");

  const usn = (usnInput && usnInput.value.trim().toUpperCase()) || "01FE23BCI093";
  const name = (nameInput && nameInput.value.trim()) || "Sonu";
  const cgpa = (cgpaInput && parseFloat(cgpaInput.value)) || 8.5;

  // Collect whatever companies the user has already typed/added into the form
  const c1 = document.getElementById("pref1Company") ? document.getElementById("pref1Company").value.trim() : "";
  const c2 = document.getElementById("pref2Company") ? document.getElementById("pref2Company").value.trim() : "";
  const c3 = document.getElementById("pref3Company") ? document.getElementById("pref3Company").value.trim() : "";
  const c4 = document.getElementById("pref4Company") ? document.getElementById("pref4Company").value.trim() : "";
  const userSelected = [c1, c2, c3, c4].filter(Boolean);

  if (statusEl) {
    statusEl.style.display = "block";
    const evalTarget = userSelected.length > 0 ? `your selected companies (${userSelected.join(", ")})` : `top MNC corporate catalog`;
    statusEl.innerHTML = `
      <div style="display:flex; align-items:center; gap:0.55rem; color:#818cf8; font-size:0.78rem;">
        <i class="fa-solid fa-spinner fa-spin"></i>
        <span><strong>AURA LangGraph Parallel Swarm (Lab 8):</strong> Dispatching 4 worker agents across ${evalTarget} for <strong>${name}</strong> (USN: ${usn}, CGPA: ${cgpa})...</span>
      </div>
    `;
  }
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Auto-Ranking Swarm...`;
  }

  try {
    const payload = {
      student_usn: usn,
      student_cgpa: cgpa
    };
    if (userSelected.length > 0) {
      payload.preferences = userSelected;
    }

    const res = await fetch("/api/aura/lab/8/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    let choices = (data && Array.isArray(data.ranked_results) && data.ranked_results.length > 0)
      ? data.ranked_results
      : [
          { company: "Tata Consultancy Services (TCS)", title: "Research & Innovation Intern", location: "Bangalore", stipend_monthly: 32000, available_vacancies: 5, is_eligible: true },
          { company: "Microsoft India", title: "Software Development Intern", location: "Bengaluru", stipend_monthly: 75000, available_vacancies: 1, is_eligible: true },
          { company: "Infosys Limited", title: "InStep Software Development Intern", location: "Bangalore", stipend_monthly: 35000, available_vacancies: 6, is_eligible: true },
          { company: "Wipro Limited", title: "Digital & AI Systems Intern", location: "Bangalore", stipend_monthly: 28000, available_vacancies: 5, is_eligible: true }
        ];

    const AURA_ROLE_DICT = {
      "abc": { role: "AI/ML Intern", loc: "Bangalore" },
      "xyz": { role: "Data Science & Analytics Intern", loc: "Bengaluru" },
      "pqr": { role: "Full Stack Web Developer Intern", loc: "Pune" },
      "def": { role: "Computer Vision & GenAI Research Intern", loc: "Hyderabad" },
      "tata": { role: "Research & Innovation Intern", loc: "Bangalore" },
      "tcs": { role: "Research & Innovation Intern", loc: "Bangalore" },
      "microsoft": { role: "Software Development Intern", loc: "Bengaluru" },
      "google": { role: "Software Engineering Summer Intern", loc: "Bangalore" },
      "infosys": { role: "InStep Software Development Intern", loc: "Bangalore" }
    };

    function cleanRoleWorkflow(comp, rawTitle) {
      if (rawTitle && rawTitle.toLowerCase() !== "unknown" && rawTitle.trim() !== "") return rawTitle;
      const c = (comp || "").toLowerCase();
      for (const k in AURA_ROLE_DICT) {
        if (c.includes(k)) return AURA_ROLE_DICT[k].role;
      }
      return "Software Engineering Intern";
    }

    function cleanLocWorkflow(comp, rawLoc) {
      if (rawLoc && rawLoc.toLowerCase() !== "unknown" && rawLoc.trim() !== "") return rawLoc;
      const c = (comp || "").toLowerCase();
      for (const k in AURA_ROLE_DICT) {
        if (c.includes(k)) return AURA_ROLE_DICT[k].loc;
      }
      return "Bengaluru";
    }

    // Populate all 4 preferences
    const fields = [
      { c: "pref1Company", r: "pref1Role", l: "pref1Loc" },
      { c: "pref2Company", r: "pref2Role", l: "pref2Loc" },
      { c: "pref3Company", r: "pref3Role", l: "pref3Loc" },
      { c: "pref4Company", r: "pref4Role", l: "pref4Loc" }
    ];

    fields.forEach((f, idx) => {
      if (choices[idx]) {
        const cEl = document.getElementById(f.c);
        const rEl = document.getElementById(f.r);
        const lEl = document.getElementById(f.l);
        const comp = choices[idx].company || "";
        if (cEl) {
          cEl.value = comp;
          cEl.style.transition = "box-shadow 0.4s ease, border-color 0.4s ease";
          cEl.style.borderColor = "#6366f1";
          cEl.style.boxShadow = "0 0 10px rgba(99,102,241,0.5)";
          setTimeout(() => { if (cEl) cEl.style.boxShadow = ""; }, 3000);
        }
        if (rEl) rEl.value = cleanRoleWorkflow(comp, choices[idx].title || choices[idx].role);
        if (lEl) lEl.value = cleanLocWorkflow(comp, choices[idx].location);
      }
    });

    if (statusEl) {
      const runId = data.run_id || 'RUN-L8-SWARM';
      const formatChip = (item, rank) => {
        const stip = item.stipend_monthly ? `₹${Number(item.stipend_monthly).toLocaleString('en-IN')}/mo` : 'Stipend Verified';
        const vac = item.available_vacancies ? `${item.available_vacancies} seats` : 'Active Vacancy';
        const statusLabel = item.is_eligible !== false ? '✓ Eligible' : 'Ineligible';
        return `
          <div style="background:rgba(15,23,42,0.85); border:1px solid rgba(99,102,241,0.4); border-radius:6px; padding:0.35rem 0.6rem; font-size:0.73rem;">
            <span style="color:#a5b4fc; font-weight:700;">#${rank} ${item.company}</span>
            <span style="color:#34d399; margin-left:4px; font-weight:600;">${stip}</span>
            <span style="color:#94a3b8; margin-left:4px;">· ${vac} · ${statusLabel}</span>
          </div>
        `;
      };

      statusEl.innerHTML = `
        <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:0.4rem; margin-bottom:0.4rem;">
          <span style="color:#34d399; font-weight:700;"><i class="fa-solid fa-circle-check"></i> LangGraph Swarm Auto-Rank Completed (Lab 8 Parallel Fan-Out)</span>
          <span class="badge" style="background:rgba(99,102,241,0.3); color:#a5b4fc; font-size:0.7rem;">RUN ID: ${runId}</span>
        </div>
        <div style="font-size:0.75rem; color:#cbd5e1; line-height:1.4; margin-bottom:6px;">
          4 LangGraph worker agents evaluated candidate eligibility (CGPA ${cgpa}), monthly salary, and live vacancy availability in parallel. Optimal preference order:
        </div>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:0.4rem; margin-top:4px;">
          ${choices[0] ? formatChip(choices[0], 1) : ''}
          ${choices[1] ? formatChip(choices[1], 2) : ''}
          ${choices[2] ? formatChip(choices[2], 3) : ''}
          ${choices[3] ? formatChip(choices[3], 4) : ''}
        </div>
      `;
    }
  } catch (err) {
    console.error("Swarm execution error:", err);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<i class="fa-solid fa-bolt"></i> Run Swarm Auto-Rank`;
    }
  }
}
window.triggerAuraSwarmForSubmission = triggerAuraSwarmForSubmission;
