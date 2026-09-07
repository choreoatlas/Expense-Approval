let current = null;

const byId = id => document.getElementById(id);

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: {"Content-Type": "application/json", ...(options.headers || {})},
    ...options,
  });
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) throw new Error(data?.error || `HTTP ${response.status}`);
  return data;
}

function payloadFromForm() {
  return {
    employee: byId("employee").value,
    amount: byId("amount").value,
    purpose: byId("purpose").value,
    receipt_ref: byId("receipt").value,
  };
}

function refreshButtons() {
  const status = current?.status;
  byId("edit-btn").disabled = status !== "draft";
  byId("submit-btn").disabled = status !== "draft";
  byId("revise-btn").disabled = status !== "rejected";
  byId("approve-btn").disabled = status !== "submitted";
  byId("reject-btn").disabled = status !== "submitted";
  byId("gm-approve-btn").disabled = status !== "manager_pending";
  byId("gm-reject-btn").disabled = status !== "manager_pending";
  byId("history-btn").disabled = !current;
}

function showCurrent() {
  byId("current").textContent = current ? JSON.stringify(current, null, 2) : "None";
  refreshButtons();
}

function showMessage(message) {
  byId("message").textContent = message;
}

byId("create-form").addEventListener("submit", async event => {
  event.preventDefault();
  try {
    current = await request("/api/expenses", {method: "POST", body: JSON.stringify(payloadFromForm())});
    showCurrent();
    showMessage("Draft created");
  } catch (error) { showMessage(error.message); }
});

byId("edit-btn").addEventListener("click", async () => {
  try {
    const payload = payloadFromForm();
    current = await request(`/api/expenses/${current.expense_id}`, {method: "PATCH", body: JSON.stringify(payload)});
    showCurrent();
    showMessage("Draft updated");
  } catch (error) { showMessage(error.message); }
});

byId("submit-btn").addEventListener("click", async () => {
  try {
    current = await request(`/api/expenses/${current.expense_id}/submit`, {method: "POST", body: "{}"});
    showCurrent();
    showMessage(`Revision ${current.revision} submitted`);
  } catch (error) { showMessage(error.message); }
});

byId("revise-btn").addEventListener("click", async () => {
  try {
    const payload = payloadFromForm();
    current = await request(`/api/expenses/${current.expense_id}/revise`, {method: "POST", body: JSON.stringify(payload)});
    showCurrent();
    showMessage(`Created revision ${current.revision}`);
  } catch (error) { showMessage(error.message); }
});

async function decide(actorId, reasonId, outcome) {
  try {
    const data = await request(`/api/expenses/${current.expense_id}/${current.revision}/decision`, {
      method: "POST",
      body: JSON.stringify({approver: byId(actorId).value, outcome, reason: byId(reasonId).value}),
    });
    current = await request(`/api/expenses/${data.expense_id}`);
    showCurrent();
    showMessage(`${data.actor_role} ${outcome} revision ${data.revision}`);
  } catch (error) { showMessage(error.message); }
}

byId("approve-btn").addEventListener("click", () => decide("approver", "approver-reason", "approved"));
byId("reject-btn").addEventListener("click", () => decide("approver", "approver-reason", "rejected"));
byId("gm-approve-btn").addEventListener("click", () => decide("general-manager", "gm-reason", "approved"));
byId("gm-reject-btn").addEventListener("click", () => decide("general-manager", "gm-reason", "rejected"));

byId("history-btn").addEventListener("click", async () => {
  try {
    const history = await request(`/api/expenses/${current.expense_id}/history`);
    byId("history").textContent = JSON.stringify(history, null, 2);
  } catch (error) { showMessage(error.message); }
});

showCurrent();
