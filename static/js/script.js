// Shared frontend logic — all data comes from the existing /api/* endpoints.
// No business logic lives here; this only calls the API and renders results.

const API_BASE = "/api";

// ---------- Search Page ----------

function initSearchPage() {
    const form = document.getElementById("search-form");
    if (!form) return;

    populateAreaDropdowns();
    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        await runSearch();
    });
}

async function runSearch() {
    const bloodGroup = document.getElementById("blood_group").value;
    const area = document.getElementById("area").value.trim();
    const eligibleOnly = document.getElementById("eligible_only").checked;

    const params = new URLSearchParams({ all: "true" }); // fetch all, split client-side
    if (bloodGroup) params.append("blood_group", bloodGroup);
    if (area) params.append("area", area);
    if (eligibleOnly) params.append("eligible_only", "true");

    const statusEl = document.getElementById("results-status");
    statusEl.textContent = "Searching...";

    try {
        const response = await fetch(`${API_BASE}/search?${params.toString()}`);
        if (!response.ok) throw new Error(`Request failed (${response.status})`);
        const results = await response.json();
        renderDonorCards(results);
        statusEl.textContent = `${results.length} donor(s) found.`;
    } catch (err) {
        statusEl.textContent = "Error fetching results: " + err.message;
    }
}

function renderDonorCards(results) {
    const availableContainer = document.getElementById("available-donors");
    const unavailableContainer = document.getElementById("unavailable-donors");
    availableContainer.innerHTML = "";
    unavailableContainer.innerHTML = "";

    if (results.length === 0) {
        availableContainer.innerHTML = `
            <div class="empty-state">
                <p>No donors found matching your filters.</p>
                <p class="hint">Try removing the area filter or choosing "Any Blood Group".</p>
            </div>`;
        return;
    }

    results.forEach((r) => {
        const donor = r.donor;
        const eligibility = r.eligibility;
        const lastDonation = eligibility.last_donation_date || "No prior donation";
        const card = document.createElement("div");
        card.className = "donor-card";
        card.innerHTML = `
            <p class="donor-id">${donor.donor_code}</p>
            <h3>${donor.full_name}</h3>
            <p><b>Blood Group:</b> ${donor.blood_group}</p>
            <p><b>Phone:</b> ${donor.phone_number}</p>
            <p><b>Area:</b> ${donor.area}</p>
            <p><b>Eligible:</b> <span class="${eligibility.is_eligible ? 'badge-yes' : 'badge-no'}">${eligibility.is_eligible ? "Yes" : "No"}</span></p>
            <p><b>Available:</b> <span class="${donor.is_available ? 'badge-yes' : 'badge-no'}">${donor.is_available ? "Yes" : "No"}</span></p>
            <p><b>Last Donation:</b> ${lastDonation}</p>
            <div class="card-actions">
                <a href="/donor/${donor.id}"><button type="button">View Details</button></a>
                ${donor.is_available ? `<button type="button" onclick="markDonationCompleted(${donor.id}, this)">Mark Donation Completed</button>` : ""}
            </div>
        `;
        (donor.is_available ? availableContainer : unavailableContainer).appendChild(card);
    });
}

async function markDonationCompleted(donorId, buttonEl) {
    const confirmed = confirm("Has this donor successfully donated blood to the patient?");
    if (!confirmed) return;

    const today = new Date().toISOString().split("T")[0];
    try {
        const response = await fetch(`${API_BASE}/donors/${donorId}/complete-donation`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ donation_date: today }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Failed to record donation");

        const card = buttonEl.closest(".donor-card");
        buttonEl.remove();
        const availabilityBadge = card.querySelector(".badge-yes");
        if (availabilityBadge) {
            availabilityBadge.className = "badge-no";
            availabilityBadge.textContent = "No";
        }
        document.getElementById("unavailable-donors").appendChild(card);
        alert("Donation recorded. Donor moved to unavailable until eligible again.");
    } catch (err) {
        alert("Error: " + err.message);
    }
}


async function viewPrediction(donorId) {
    try {
        const response = await fetch(`${API_BASE}/prediction/${donorId}`);
        if (!response.ok) throw new Error(`Request failed (${response.status})`);
        const result = await response.json();
        alert(
            `Response Likelihood: ${(result.response_likelihood * 100).toFixed(1)}%\n` +
            `Confidence: ${result.confidence_label}`
        );
    } catch (err) {
        alert("Could not fetch prediction: " + err.message);
    }
}

function switchMode(mode) {
    const addSection = document.getElementById("mode-add");
    const updateSection = document.getElementById("mode-update");
    const addTab = document.getElementById("tab-add");
    const updateTab = document.getElementById("tab-update");

    addSection.classList.toggle("active", mode === "add");
    updateSection.classList.toggle("active", mode === "update");

    addTab.classList.toggle("active", mode === "add");
    updateTab.classList.toggle("active", mode === "update");
    addTab.setAttribute("aria-selected", mode === "add");
    updateTab.setAttribute("aria-selected", mode === "update");
}

function initRegisterPage() {
    const donorForm = document.getElementById("donor-form");
    const lookupForm = document.getElementById("lookup-form");
    const updateForm = document.getElementById("update-form");
    const donationForm = document.getElementById("record-donation-form");
    if (!donorForm) return;

    populateAreaDropdowns();
    donorForm.addEventListener("submit", (e) => { e.preventDefault(); submitDonor(); });
    lookupForm.addEventListener("submit", (e) => { e.preventDefault(); lookupDonor(); });
    updateForm.addEventListener("submit", (e) => { e.preventDefault(); saveDonorUpdate(); });
    donationForm.addEventListener("submit", (e) => { e.preventDefault(); recordDonation(); });
}

// ---------- Mode 2: Lookup ----------

async function lookupDonor() {
    const donorId = document.getElementById("lookup_donor_id").value;
    const phone = document.getElementById("lookup_phone_number").value;
    const statusEl = document.getElementById("lookup-status");
    const panel = document.getElementById("update-panel");

    const params = new URLSearchParams();
    if (donorId) params.append("donor_id", donorId);
    if (phone) params.append("phone_number", phone);

    try {
        const response = await fetch(`${API_BASE}/donors/lookup?${params.toString()}`);
        const donor = await response.json();
        if (!response.ok) throw new Error(donor.error || "Donor not found");

        panel.classList.remove("update-panel-hidden");
        panel.classList.add("update-panel-visible");

        document.getElementById("update_donor_id").value = donor.id;
        document.getElementById("update_area").value = donor.area;
        document.getElementById("update_phone_number").value = donor.phone_number;
        document.getElementById("update_is_available").checked = donor.is_available;
        document.getElementById("update-readonly-info").innerHTML = `
            <b>${donor.full_name}</b> (${donor.donor_code}) — ${donor.blood_group} — DOB: ${donor.date_of_birth}
        `;
        statusEl.textContent = "";
    } catch (err) {
        panel.classList.remove("update-panel-visible");
        panel.classList.add("update-panel-hidden");
        statusEl.textContent = "Error: " + err.message;
        statusEl.style.color = "#b71c1c";
    }
}

async function saveDonorUpdate() {
    const donorId = document.getElementById("update_donor_id").value;
    const payload = {
        area: document.getElementById("update_area").value,
        phone_number: document.getElementById("update_phone_number").value,
        is_available: document.getElementById("update_is_available").checked,
    };
    const statusEl = document.getElementById("update-status");
    try {
        const response = await fetch(`${API_BASE}/donors/${donorId}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Update failed");
        statusEl.textContent = "Profile updated successfully.";
        statusEl.style.color = "#1b7a1b";
    } catch (err) {
        statusEl.textContent = "Error: " + err.message;
        statusEl.style.color = "#b71c1c";
    }
}

async function recordDonation() {
    const donorId = document.getElementById("update_donor_id").value;
    const payload = {
        donation_date: document.getElementById("donation_date").value,
        volume_ml: document.getElementById("donation_volume_ml").value
            ? parseInt(document.getElementById("donation_volume_ml").value, 10) : null,
    };
    const statusEl = document.getElementById("donation-status");
    try {
        // Reuses the same completion workflow as the search page's
        // "Mark Donation Completed" action — single source of truth.
        const response = await fetch(`${API_BASE}/donors/${donorId}/complete-donation`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Failed to record donation");
        statusEl.textContent = `Donation recorded. Total donations: ${data.total_donations}. Donor marked unavailable.`;
        statusEl.style.color = "#1b7a1b";
        document.getElementById("update_is_available").checked = false;
    } catch (err) {
        statusEl.textContent = "Error: " + err.message;
        statusEl.style.color = "#b71c1c";
    }
}


// ---------- Age calc + client-side validation (Register page) ----------

function updateAgeDisplay() {
    const dob = document.getElementById("date_of_birth").value;
    if (!dob) return;
    const age = calculateAge(new Date(dob));
    document.getElementById("age_display").value = age >= 0 ? `${age} years` : "Invalid";
}

function calculateAge(dobDate) {
    const today = new Date();
    let age = today.getFullYear() - dobDate.getFullYear();
    const m = today.getMonth() - dobDate.getMonth();
    if (m < 0 || (m === 0 && today.getDate() < dobDate.getDate())) age--;
    return age;
}

function validateDonorForm(payload) {
    const errors = [];
    if (!payload.full_name.trim()) errors.push("Full name is required.");
    if (!payload.date_of_birth) errors.push("Date of birth is required.");
    else if (new Date(payload.date_of_birth) > new Date()) errors.push("Date of birth cannot be in the future.");
    if (!payload.blood_group) errors.push("Blood group is required.");
    if (!/^\d{7,15}$/.test(payload.phone_number)) errors.push("Phone must be 7–15 digits.");
    if (!payload.area.trim()) errors.push("Area is required.");
    return errors;
}

// ---------- Extended submitDonor ----------

async function submitDonor() {
    const payload = {
        full_name: document.getElementById("full_name").value,
        date_of_birth: document.getElementById("date_of_birth").value,
        gender: document.getElementById("gender").value || null,
        blood_group: document.getElementById("blood_group").value,
        phone_number: document.getElementById("phone_number").value,
        area: document.getElementById("area").value,
        is_available: document.getElementById("is_available").checked,
    };

    const errorsEl = document.getElementById("form-errors");
    const clientErrors = validateDonorForm(payload);
    if (clientErrors.length) {
        errorsEl.textContent = clientErrors.join(" ");
        return;
    }
    errorsEl.textContent = "";

    const statusEl = document.getElementById("donor-status");
    try {
        const response = await fetch(`${API_BASE}/donors`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Failed to register donor");
        statusEl.innerHTML = `
            Registration Successful<br>
            Donor ID: <b id="new-donor-code">${data.donor_code}</b>
            <button type="button" onclick="copyDonorCode()">Copy</button>
        `;
        statusEl.style.color = "#1b7a1b";
    } catch (err) {
        statusEl.textContent = "Error: " + err.message;
        statusEl.style.color = "#b71c1c";
    }
}

function copyDonorCode() {
    const code = document.getElementById("new-donor-code").textContent;
    navigator.clipboard.writeText(code);
}


// ---------- Dashboard ----------

let bloodGroupChartInstance = null;
let eligibilityChartInstance = null;

async function initDashboardPage() {
    await refreshDashboard();
    setInterval(refreshDashboard, 15000); // poll every 15s — no page reload, no restart needed
}

async function refreshDashboard() {
    try {
        const response = await fetch(`${API_BASE}/dashboard`);
        const stats = await response.json();

        document.getElementById("total_donors").textContent = stats.total_donors;
        document.getElementById("eligible_today").textContent = stats.eligible_today;
        document.getElementById("available_donors").textContent = stats.available_donors;
        document.getElementById("donations_today").textContent = stats.donations_today ?? 0;

        renderAreaHeatmap(stats.area_counts);
        renderBloodGroupChart(stats.blood_group_counts);
        renderEligibilityChart(stats.eligible_today, stats.not_eligible_today);
        loadDashboardDonorTable();
    } catch (err) {
        console.error("Dashboard refresh failed:", err);
    }
}

async function loadDashboardDonorTable() {
    try {
        const response = await fetch(`${API_BASE}/donors`);
        const donors = await response.json();
        const body = document.getElementById("dashboard-donor-table-body");
        if (body) {
            body.innerHTML = donors.slice(0, 10).map(d => `
                <tr><td>${d.donor_code}</td><td>${d.full_name}</td><td>${d.blood_group}</td><td>${d.area}</td></tr>
            `).join("");
        }
    } catch (err) {
        console.error("Failed to load dashboard donor table:", err);
    }
}

function renderAreaHeatmap(areaCounts) {
    const container = document.getElementById("area-heatmap");
    if (!container || !areaCounts) return;
    const max = Math.max(...Object.values(areaCounts), 1);

    container.innerHTML = Object.entries(areaCounts)
        .sort((a, b) => b[1] - a[1])
        .map(([area, count]) => {
            const intensity = count / max;
            const bg = `rgba(183, 28, 28, ${0.15 + intensity * 0.75})`;
            const textColor = intensity > 0.5 ? "white" : "#333";
            return `
                <div class="heatmap-cell" style="background:${bg}; color:${textColor}">
                    <span class="heatmap-area">${area}</span>
                    <span class="heatmap-count">${count}</span>
                </div>`;
        })
        .join("");
}

function renderBloodGroupChart(bloodGroupCounts) {
    if (bloodGroupChartInstance) bloodGroupChartInstance.destroy(); // prevent duplicate canvases stacking
    const ctx = document.getElementById("bloodGroupChart");
    if (!ctx || !bloodGroupCounts) return;
    bloodGroupChartInstance = new Chart(ctx, {
        type: "bar",
        data: {
            labels: Object.keys(bloodGroupCounts),
            datasets: [{
                label: "Donors",
                data: Object.values(bloodGroupCounts),
                backgroundColor: "#b71c1c",
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } },
        },
    });
}

function renderEligibilityChart(eligible, notEligible) {
    if (eligibilityChartInstance) eligibilityChartInstance.destroy();
    const ctx = document.getElementById("eligibilityChart");
    if (!ctx) return;
    eligibilityChartInstance = new Chart(ctx, {
        type: "doughnut",
        data: {
            labels: ["Eligible", "Not Eligible"],
            datasets: [{
                data: [eligible, notEligible],
                backgroundColor: ["#1b7a1b", "#b71c1c"],
            }],
        },
        options: { responsive: true, maintainAspectRatio: false },
    });
}

// ---------- Donor Details ----------

async function initDonorDetailsPage(donorId) {
    try {
        const response = await fetch(`${API_BASE}/donors/${donorId}/details`);
        if (!response.ok) throw new Error("Donor not found");
        const data = await response.json();

        document.getElementById("donor-name").textContent = data.donor.full_name;
        document.getElementById("donor-profile").innerHTML = `
            <p><b>Blood Group:</b> ${data.donor.blood_group}</p>
            <p><b>Gender:</b> ${data.donor.gender || "Prefer not to say"}</p>
            <p><b>Area:</b> ${data.donor.area}</p>
            <p><b>Phone:</b> ${data.donor.phone_number}</p>
            <p><b>Available:</b> ${data.donor.is_available ? "Yes" : "No"}</p>
            <p><b>Total Donations:</b> ${data.total_donations}</p>
            <p><b>Last Donation:</b> ${data.last_donation_date || "No prior donations"}</p>
        `;

        const e = data.eligibility;
        document.getElementById("eligibility-card").innerHTML = `
            <p><b>Eligible:</b> <span class="${e.is_eligible ? 'badge-yes' : 'badge-no'}">${e.is_eligible ? "Yes" : "No"}</span></p>
            <p><b>Last Donation:</b> ${e.last_donation_date || "N/A"}</p>
            <p><b>Next Eligible Date:</b> ${e.next_eligible_date || "N/A"}</p>
            <p><b>Days Remaining:</b> ${e.days_remaining ?? "0"}</p>
            <p><b>Reason:</b> ${e.reason}</p>
        `;

        // Manual verification — plain-language walkthrough of the same numbers above
        if (e.last_donation_date) {
            const last = new Date(e.last_donation_date);
            const today = new Date();
            const daysPassed = Math.floor((today - last) / (1000 * 60 * 60 * 24));
            document.getElementById("manual-verification").innerHTML = `
                <p>Last Donation: <b>${e.last_donation_date}</b></p>
                <p>Days Passed Since Then: <b>${daysPassed}</b></p>
                <p>Eligibility Interval Required: <b>90 days</b> (configurable)</p>
                <p>${daysPassed} ${daysPassed >= 90 ? "≥" : "<"} 90 → Eligible: <b>${daysPassed >= 90 ? "Yes" : "No"}</b></p>
            `;
        } else {
            document.getElementById("manual-verification").innerHTML =
                "<p>No prior donation on record → first-time donor → eligible by default.</p>";
        }

        document.getElementById("history-link").href = `/donations/${donorId}`;

        document.getElementById("predict-btn").addEventListener("click", async () => {
            const predResponse = await fetch(`${API_BASE}/prediction/${donorId}`);
            const pred = await predResponse.json();
            document.getElementById("prediction-card").innerHTML = `
                <p><b>Response Probability:</b> ${(pred.response_likelihood * 100).toFixed(1)}%</p>
                <p><b>Confidence:</b> ${pred.confidence_label}</p>
                <p><b>Explanation:</b> Based on eligibility status, availability, and recency of last donation, the model estimates this donor's likelihood of responding to an emergency request.</p>
            `;
        });
    } catch (err) {
        document.getElementById("donor-profile").textContent = "Error loading donor: " + err.message;
    }
}

// ---------- Donation History ----------

async function initHistoryPage(donorId) {
    const statusEl = document.getElementById("history-status");
    try {
        const response = await fetch(`${API_BASE}/donors/${donorId}/donations`);
        if (!response.ok) throw new Error("Could not load history");
        const donations = await response.json();

        const body = document.getElementById("history-body");
        if (donations.length === 0) {
            statusEl.textContent = "No donations recorded for this donor yet.";
            return;
        }
        donations.forEach((d) => {
            const row = document.createElement("tr");
            row.innerHTML = `<td>${d.donation_date}</td><td>${d.location || "—"}</td><td>${d.volume_ml || "—"}</td>`;
            body.appendChild(row);
        });
        statusEl.textContent = `${donations.length} donation record(s) — full history, most recent first.`;
    } catch (err) {
        statusEl.textContent = "Error: " + err.message;
    }
}

// ---------- Constraint Demo ----------

async function postAndShow(url, payload) {
    const output = document.getElementById("demo-output");
    try {
        const response = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const data = await response.json();
        output.textContent = `Status: ${response.status}\n\n${JSON.stringify(data, null, 2)}`;
    } catch (err) {
        output.textContent = "Request failed: " + err.message;
    }
}

function demoDuplicatePhone() {
    const payload = {
        full_name: "Duplicate Test", date_of_birth: "1995-01-01",
        blood_group: "O+", phone_number: "9123456789", area: "Test Area",
    };
    // Sends the same request twice — second one triggers the UNIQUE constraint
    postAndShow(`${API_BASE}/donors`, payload).then(() => postAndShow(`${API_BASE}/donors`, payload));
}

function demoFutureDate() {
    postAndShow(`${API_BASE}/donations`, { donor_id: 1, donation_date: "2099-01-01" });
}

function demoInvalidAge() {
    postAndShow(`${API_BASE}/donors`, {
        full_name: "Too Young", date_of_birth: "2020-01-01",
        blood_group: "O+", phone_number: "9123456700", area: "Test Area",
    });
}

function demoForeignKey() {
    postAndShow(`${API_BASE}/donations`, { donor_id: 999999, donation_date: "2026-01-01" });
}

// ---------- Assistant Page ----------

function initAssistantPage() {
    const form = document.getElementById("assistant-form");
    if (!form) return;

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        await sendAssistantQuery();
    });
}

async function sendAssistantQuery() {
    const input = document.getElementById("assistant-query");
    const query = input.value.trim();
    if (!query) return;

    appendChatMessage("user", query);
    input.value = "";

    try {
        const response = await fetch(`${API_BASE}/assistant`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query }),
        });
        const data = await response.json();
        appendChatMessage("bot", data.answer);
    } catch (err) {
        appendChatMessage("bot", "Error reaching the assistant: " + err.message);
    }
}

function appendChatMessage(sender, text) {
    const chatWindow = document.getElementById("chat-window");
    const msg = document.createElement("div");
    msg.className = `chat-message ${sender}`;
    const formattedText = text.replace(/\n/g, "<br>");  // NEW — preserve line breaks from assistant cards
    msg.innerHTML = `<span class="label">${sender === "user" ? "You" : "Assistant"}</span>${formattedText}`;
    chatWindow.appendChild(msg);
    chatWindow.scrollTop = chatWindow.scrollHeight;
}

async function populateAreaDropdowns() {
    try {
        const response = await fetch(`${API_BASE}/areas`);
        const areas = await response.json();
        document.querySelectorAll("select.area-select").forEach((select) => {
            const firstOpt = select.querySelector("option");
            select.innerHTML = "";
            if (firstOpt) {
                select.appendChild(firstOpt);
            }
            areas.forEach((area) => {
                const opt = document.createElement("option");
                opt.value = area;
                opt.textContent = area;
                select.appendChild(opt);
            });
        });
    } catch (err) {
        console.error("Failed to load area list:", err);
    }
}