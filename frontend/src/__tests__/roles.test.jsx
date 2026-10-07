import { render, screen, waitFor, cleanup } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../context/AuthContext";
import Leads from "../pages/Leads";
import Team from "../pages/Team";

const USERS = [
  { id: "u1", name: "Asha Admin", email: "asha@x.com", role: "ADMIN", is_active: true },
  { id: "u2", name: "Vik Viewer", email: "vik@x.com", role: "VIEWER", is_active: true },
];

function mockApi(role) {
  const me = USERS.find((u) => u.role === role) || { id: "m", name: "Mia", role, is_active: true };
  globalThis.fetch = vi.fn(async (url) => {
    const path = String(url);
    const body =
      path.endsWith("/users/me") ? me :
      path.endsWith("/users") ? USERS :
      path.includes("/jobs") ? [] :
      path.includes("/leads") ? { items: [], total: 0, page: 1, page_size: 20, total_pages: 0 } : {};
    return { ok: true, status: 200, json: async () => body };
  });
}

function renderAs(role, ui) {
  localStorage.setItem("crm_token", "t");
  mockApi(role);
  return render(<AuthProvider><MemoryRouter>{ui}</MemoryRouter></AuthProvider>);
}

beforeEach(() => localStorage.clear());
afterEach(cleanup);

describe("role-aware controls", () => {
  it("viewer sees the leads list but no discover / bulk-audit controls", async () => {
    renderAs("VIEWER", <Leads />);
    await screen.findByText("Leads");
    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalledWith(expect.stringContaining("/users/me"), expect.anything()));
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByText("Search leads on Google Maps")).toBeNull();
    expect(screen.queryByText("Audit unaudited leads")).toBeNull();
  });

  it("sales executive gets discover and bulk-audit", async () => {
    renderAs("SALES_EXECUTIVE", <Leads />);
    expect(await screen.findByText("Search leads on Google Maps")).toBeTruthy();
    expect(await screen.findByText("Audit unaudited leads")).toBeTruthy();
  });

  it("admin can add members; the team list renders", async () => {
    renderAs("ADMIN", <Team />);
    expect(await screen.findByText("Vik Viewer")).toBeTruthy();
    expect(await screen.findByText("Add member")).toBeTruthy();
    expect(screen.getAllByText("Reset password").length).toBeGreaterThan(0);
  });

  it("manager sees the team but not the admin controls", async () => {
    renderAs("SALES_MANAGER", <Team />);
    expect(await screen.findByText("Vik Viewer")).toBeTruthy();
    await screen.findByText(/Only admins can add or change/);
    expect(screen.queryByText("Add member")).toBeNull();
  });
});
