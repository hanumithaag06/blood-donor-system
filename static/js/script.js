// Shared frontend logic — all data comes from the existing /api/* endpoints.
// No business logic lives here; this only calls the API and renders results.

const API_BASE = "/api";

// ---------- Search Page ----------

function initSearchPage() {
    const form = document.getElementById("search-form");
    if (!form) return;

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        await runSearch();
    });
}

async function runSearch() {
    const bloodGroup = document.getElementById("blood_group").value;
    const area = document.getElementById("area").value.trim();
    const eligibleOnly = document.getElementById("eligible_only").checked;
    const availableOnly = document.getElementById("available_only").checked;

    const params = new URLSearchParams();
    if (bloodGroup) params.append("blood_group", bloodGroup);
    if (area) params.append("area", area);
    if (eligibleOnly) params.append("eligible_only", "true");
    if (availableOnly) params.append("available_only", "true");

    const statusEl = document.getElementById("results-status");
    statusEl.textContent = "Searching...";

    try {
        const response = await fetch(`${API_BASE}/search?${params.toString()}`);
        if (!response.ok) throw new Error(`Request failed (${response.status})`);
        const results = await response.json();
        renderResults(results);
        statusEl.textContent = `${results.length} donor(s) found.`;
    } catch (err) {
        statusEl.textContent = "Error fetching results: " + err.message;
    }
}

function renderResults(results) {
    const body = document.getElementById("results-body");
    body.innerHTML = "";

    if (results.length === 0) {
        document.getElementById("results-status").innerHTML = `
            <div class="empty-state">
                <p>No donors found matching your filters.</p>
                <p class="hint">Try removing the area filter, choosing "Any Blood Group", or unchecking "Eligible only".</p>
            </div>`;
        return;
    }

    results.forEach((r) => {
        const donor = r.donor;
        const eligibility = r.eligibility;
        const row = document.createElement("tr");
        row.innerHTML = `
            <td><a href="/donor/${donor.id}">${donor.full_name}</a></td>
            <td>${donor.blood_group}</td>
            <td>${donor.area}</td>
            <td class="${eligibility.is_eligible ? 'badge-yes' : 'badge-no'}">${eligibility.is_eligible ? "Yes" : "No"}</td>
            <td class="${donor.is_available ? 'badge-yes' : 'badge-no'}">${donor.is_available ? "Yes" : "No"}</td>
            <td>${(r.prediction_score * 100).toFixed(0)}%</td>
            <td>${eligibility.reason}</td>
        `;
        body.appendChild(row);
    });
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

// ---------- Register Page ----------

function initRegisterPage() {
    const donorForm = document.getElementById("donor-form");
    const donationForm = document.getElementById("donation-form");
    if (!donorForm) return;

    donorForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        await submitDonor();
    });

    donationForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        await submitDonation();
    });
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
    if (!/^\d{7,15}$/.test(payload.phone)) errors.push("Phone must be 7–15 digits.");
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
        phone: document.getElementById("phone").value,
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

        // If a last donation date was provided, log it via the existing donations endpoint
        const lastDonation = document.getElementById("last_donation_date").value;
        if (lastDonation) {
            await fetch(`${API_BASE}/donations`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ donor_id: data.id, donation_date: lastDonation }),
            });
        }

        statusEl.textContent = `Registered donor #${data.id} — ${data.full_name}`;
        statusEl.style.color = "#1b7a1b";
    } catch (err) {
        statusEl.textContent = "Error: " + err.message;
        statusEl.style.color = "#b71c1c";
    }
}

async function submitDonation() {
    const payload = {
        donor_id: parseInt(document.getElementById("donor_id").value, 10),
        donation_date: document.getElementById("donation_date").value,
        volume_ml: document.getElementById("volume_ml").value
            ? parseInt(document.getElementById("volume_ml").value, 10)
            : null,
    };

    const statusEl = document.getElementById("donation-status");
    try {
        const response = await fetch(`${API_BASE}/donations`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Failed to log donation");
        statusEl.textContent = `Donation #${data.id} logged for donor #${data.donor_id}`;
        statusEl.style.color = "#1b7a1b";
    } catch (err) {
        statusEl.textContent = "Error: " + err.message;
        statusEl.style.color = "#b71c1c";
    }
}

// ---------- Dashboard ----------

async function initDashboardPage() {
    try {
        const response = await fetch(`${API_BASE}/dashboard`);
        const stats = await response.json();

        document.getElementById("total_donors").textContent = stats.total_donors;
        document.getElementById("eligible_today").textContent = stats.eligible_today;
        document.getElementById("available_donors").textContent = stats.available_donors;
        document.getElementById("rare_blood_donors").textContent = stats.rare_blood_donors;

        renderAreaHeatmap(stats.area_counts);
        renderBloodGroupChart(stats.blood_group_counts);
        renderEligibilityChart(stats.eligible_today, stats.not_eligible_today);
    } catch (err) {
        console.error("Dashboard load failed:", err);
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
    const ctx = document.getElementById("bloodGroupChart");
    if (!ctx || !bloodGroupCounts) return;
    new Chart(ctx, {
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
            plugins: { legend: { display: false } },
            scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } },
        },
    });
}

function renderEligibilityChart(eligible, notEligible) {
    const ctx = document.getElementById("eligibilityChart");
    if (!ctx) return;
    new Chart(ctx, {
        type: "doughnut",
        data: {
            labels: ["Eligible", "Not Eligible"],
            datasets: [{
                data: [eligible, notEligible],
                backgroundColor: ["#1b7a1b", "#b71c1c"],
            }],
        },
        options: { responsive: true },
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
            <p><b>Phone:</b> ${data.donor.phone}</p>
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
        blood_group: "O+", phone: "9123456789", area: "Test Area",
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
        blood_group: "O+", phone: "9123456700", area: "Test Area",
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
    msg.innerHTML = `<span class="label">${sender === "user" ? "You" : "Assistant"}</span>${text}`;
    chatWindow.appendChild(msg);
    chatWindow.scrollTop = chatWindow.scrollHeight;
}