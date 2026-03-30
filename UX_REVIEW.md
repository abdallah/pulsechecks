# PulseChecks UX Review

**Date:** 2026-03-25  
**Scope:** Frontend codebase (`./frontend/src`) — pages and components  
**Audience:** Engineers using PulseChecks to monitor scheduled jobs

---

## Priority Definitions

- **P1** — Blocks core workflows or causes data loss risk; fix immediately
- **P2** — Meaningfully degrades usability; fix in next sprint
- **P3** — Polish, consistency, or nice-to-have improvements

---

## P1 Issues

### P1-1: `alert()` / `confirm()` used for all errors and destructive confirmations
**Where:** Every page — `ChecksPage`, `CheckDetailPage`, `TeamSettingsPage`, `AlertChannelsPage`, `SharedAlertsPage`  
**Description:** All error feedback and destructive-action confirmations use native browser `alert()` and `confirm()` dialogs. These are visually jarring, block the thread, cannot be styled, and are suppressed in some browser/iframe contexts. On mobile they look broken. For an engineer-facing tool this reads as unfinished.  
**Suggested fix:** Replace with inline error banners (for errors) and modal dialogs (for confirmations). The delete-check and rotate-token flows already have proper modals — apply that same pattern everywhere else. A simple toast/notification component would handle success messages.

---

### P1-2: Token rotation success shown via `alert()` with no way to copy the new URL in-context
**Where:** `ChecksPage.jsx` → `handleRotateToken`; `CheckDetailPage.jsx` → `handleRotateToken`  
**Description:** After rotating a token the user is told "please update your monitoring scripts" via an `alert()`. The new ping URL is not shown in the alert, and the user must dismiss the dialog and then find the updated URL in the UI. If they accidentally close the tab or navigate away before copying, they have to come back. This is a high-stakes moment — the old URL is already dead.  
**Suggested fix:** After rotation, show a modal or inline callout that displays the new ping URL with a one-click copy button, and requires explicit acknowledgement before dismissing.

---

### P1-3: No error state when checks or teams fail to load
**Where:** `DashboardPage.jsx` → `loadTeams`; `ChecksPage.jsx` → `loadChecks`  
**Description:** If the API call fails, `loading` is set to `false` and the empty-state UI ("No teams" / "No checks") is shown — indistinguishable from a genuinely empty account. The user has no idea whether they have no data or whether the app is broken.  
**Suggested fix:** Track a separate `error` state. On failure, show a distinct error state with a retry button instead of the empty-state component.

---

### P1-4: Shared channel creation silently picks the user's first team
**Where:** `SharedAlertsPage.jsx` → `handleCreateChannel`  
**Description:** When creating a shared channel from the Shared Alerts page, the code silently assigns it to `teams[0]`. If the user belongs to multiple teams, the channel ends up in an arbitrary team with no indication of which one. There is no way to choose.  
**Suggested fix:** Add a "Owning team" dropdown to the create-shared-channel form, pre-populated with the user's teams.

---

## P2 Issues

### P2-1: Alert channels management is duplicated across three places with no clear canonical home
**Where:** `TeamSettingsPage` (Alerts tab), `AlertChannelsPage`, `SharedAlertsPage`  
**Description:** Alert channels can be created, edited, and deleted from Team Settings → Alert Channels tab, from the dedicated `/teams/:id/channels` route, and shared channels from `/shared-alerts`. These three surfaces have slightly different forms and behaviours. Engineers will not know which one to use, and changes in one place may not be immediately obvious in another.  
**Suggested fix:** Consolidate to one canonical location (the dedicated `AlertChannelsPage` is the most complete). Remove the duplicate form from `TeamSettingsPage` and replace it with a link to the channels page. Keep `SharedAlertsPage` as a read-only cross-team view.

---

### P2-2: Period and grace time inputs are in minutes but stored/displayed inconsistently
**Where:** `ChecksPage.jsx` create form and quick-edit modal; `CheckDetailPage.jsx` detail view  
**Description:** The create/edit forms accept minutes (converting to seconds internally), but the detail view displays the raw `formatDuration` output (e.g. "60m", "5m"). A user who sets "1440 minutes" will see "24h" on the detail page — not wrong, but the unit mismatch between input and display creates cognitive friction. More critically, there is no minimum validation on the grace period — `min="0"` allows a zero-grace check, which will alert immediately on any missed ping.  
**Suggested fix:** Show the same human-readable format in the form inputs (or use a duration picker). Add a note that grace=0 means instant alerting. Consider a minimum of 1 minute for grace.

---

### P2-3: Bulk actions bar is always visible even with zero checks selected, and only supports "Pause" — not "Resume"
**Where:** `ChecksPage.jsx`  
**Description:** The bulk actions bar renders whenever there are any checks, even before anything is selected. The "Pause (N)" and "Resume (N)" buttons appear only after selection, but the bar itself takes up space and adds visual noise at all times. Additionally, `handleBulkResume` is referenced in the JSX but not defined in the component — this is a runtime error.  
**Suggested fix:** Hide the bulk actions bar until at least one check is selected (slide it in). Define `handleBulkResume` or remove the Resume bulk button until it is implemented.

---

### P2-4: Check detail page "Alert Configuration" section is collapsed by default with no indication of current state
**Where:** `CheckDetailPage.jsx`  
**Description:** The alert channels section is hidden behind a "Configure" toggle. If a check has no alert channels configured, there is no visible warning — the user may not realise alerts are silently disabled. The "Active channels: N" green callout only appears inside the collapsed section.  
**Suggested fix:** Show a summary line in the section header even when collapsed: e.g. "2 channels active" (green) or "No channels — alerts disabled" (amber warning). This gives at-a-glance status without requiring expansion.

---

### P2-5: Ping history shows "Latest 20" with no pagination or load-more
**Where:** `CheckDetailPage.jsx`  
**Description:** The ping list is hard-capped at 20 entries with no way to see older pings. For engineers debugging a job that failed days ago, this is a dead end. The heading literally says "Latest 20" which signals the limitation but offers no escape.  
**Suggested fix:** Add a "Load more" button or simple pagination. Even a date-range filter would be valuable for debugging.

---

### P2-6: "No pings yet" empty state gives no actionable guidance
**Where:** `CheckDetailPage.jsx`  
**Description:** When a check has never been pinged, the UI shows "No pings recorded yet" — a plain text message with no next step. For a new user this is a dead end; they don't know what to do next.  
**Suggested fix:** Promote the "Usage Example" curl snippet (which already exists lower on the page) into the empty state, or add a direct link to it. Something like: "No pings yet — send your first ping using the URL above."

---

### P2-7: Loading state on initial app load shows plain "Loading..." text
**Where:** `App.jsx`  
**Description:** While the app resolves authentication, it renders a plain `<div>Loading...</div>` with no spinner or branding. This looks broken on slow connections.  
**Suggested fix:** Use the same spinner pattern used elsewhere (`animate-spin` border div) and optionally show the Pulsechecks logo/wordmark.

---

### P2-8: Navigation has no active-state indicator and no breadcrumbs
**Where:** `Layout.jsx`, all pages  
**Description:** The nav bar only shows the logo and logout button. There is no indication of where the user currently is. Deep pages (e.g. a check detail) use back-button links, but there is no breadcrumb trail. On `ChecksPage` the team name is embedded in the `<h1>` as a clickable link, which is non-standard and easy to miss.  
**Suggested fix:** Add a breadcrumb component: `Teams > {Team Name} > Checks > {Check Name}`. This also removes the need for the awkward team-name-as-link pattern in headings.

---

### P2-9: Delete actions on icon-only buttons have no visible label
**Where:** `ChecksPage.jsx` (per-row action buttons), `AlertChannelsPage.jsx`, `TeamSettingsPage.jsx`  
**Description:** The per-check action buttons (pause, edit, rotate, delete) are icon-only with `title` attributes for tooltips. Tooltips are not discoverable on touch devices and require hover dwell time on desktop. The delete (trash) icon sits immediately next to the rotate and settings icons with no visual separation — a misclick deletes a check.  
**Suggested fix:** Add visible text labels to destructive actions, or at minimum add more visual separation (spacing, colour) between the delete button and adjacent safe actions. Consider moving delete into a dropdown/overflow menu.

---

### P2-10: `console.log` debug statements left in production code
**Where:** `TeamSettingsPage.jsx` (`loadAlerts`, `loadChannels`), `App.jsx` (`loadUser`)  
**Description:** Multiple `console.log` calls expose internal data structures and token prefixes in the browser console. This is a minor security concern and signals unfinished code to engineers inspecting the console.  
**Suggested fix:** Remove all `console.log` debug statements. Keep `console.error` for genuine error logging.

---

## P3 Issues

### P3-1: Empty states use a generic icon and minimal copy
**Where:** `DashboardPage` ("No teams"), `ChecksPage` ("No checks"), `AlertChannelsPage` ("No alert channels")  
**Description:** All empty states follow the same minimal pattern: grey icon, one-line heading, one-line subtext. There is no CTA button embedded in the empty state itself — the user must scroll up to find the "New Team" / "New Check" button.  
**Suggested fix:** Embed a primary CTA button directly in the empty state card. For "No checks", consider a short onboarding blurb explaining what a check is and linking to docs.

---

### P3-2: "Shared Alerts" button in the dashboard header is visually ambiguous
**Where:** `DashboardPage.jsx`  
**Description:** The "Shared Alerts" button uses a custom inline SVG arrow icon that doesn't match the Lucide icon set used everywhere else. It sits next to "New Team" but navigates to a completely different section, which is confusing.  
**Suggested fix:** Use a Lucide icon (e.g. `Share2` or `Bell`) consistent with the rest of the UI. Consider moving "Shared Alerts" to the nav bar or a sidebar rather than the dashboard header.

---

### P3-3: "Shared" badge is rendered twice on channel list items
**Where:** `TeamSettingsPage.jsx` → alerts tab channel list  
**Description:** The "Shared" green badge is rendered in both the channel name line and the channel detail line for the same item, resulting in two identical badges side by side.  
**Suggested fix:** Remove the duplicate badge from the detail line.

---

### P3-4: Status badges use ALL CAPS but status icons use colour only — no text for screen readers
**Where:** `ChecksPage.jsx` → `getStatusBadge` / `getStatusIcon`  
**Description:** The status icon (coloured circle) conveys status by colour alone with no accessible label. Screen readers and colour-blind users rely on the badge text, but the icon has no `aria-label`.  
**Suggested fix:** Add `aria-label={check.status}` to the status icon. Consider adding a short text label next to the icon on the list view.

---

### P3-5: Period and grace time have no preset/quick-select options
**Where:** `ChecksPage.jsx` create form, quick-edit modal  
**Description:** Engineers commonly monitor jobs on standard schedules (every 5m, 15m, 1h, 24h). The free-form number input requires mental arithmetic to convert. Competitors (Healthchecks.io, Cronitor) offer preset buttons.  
**Suggested fix:** Add quick-select preset chips below the period input: "5m · 15m · 1h · 6h · 24h". Clicking a preset fills the input.

---

### P3-6: Login page exposes auth provider implementation detail
**Where:** `LoginPage.jsx`  
**Description:** The footer text reads "Secure authentication via Firebase Auth" or "AWS Cognito" depending on the deployment. This is an internal implementation detail that is irrelevant to end users and may cause confusion if the provider changes.  
**Suggested fix:** Replace with a generic "Secure authentication via Google Workspace SSO" message.

---

### P3-7: `CheckDetailPage` uses emoji for delete and rotate buttons inconsistently
**Where:** `CheckDetailPage.jsx` header actions  
**Description:** The "Delete" button uses a 🗑️ emoji and the rotate token button uses a 🔄 emoji, while all other buttons in the app use Lucide icons. This is visually inconsistent and emojis render differently across operating systems.  
**Suggested fix:** Replace emoji with the corresponding Lucide icons (`Trash2`, `RotateCcw`) already imported in the file.

---

### P3-8: No confirmation that a member invitation was sent
**Where:** `TeamSettingsPage.jsx` → `handleAddMember`  
**Description:** After adding a member by email, the form closes and the member list reloads. If the invite was sent successfully, there is no success message. If the email doesn't exist in the system, the error is shown via `alert()`. The user has no positive confirmation.  
**Suggested fix:** Show an inline success message ("Invitation sent to user@example.com") after the form closes.

---

### P3-9: `SharedAlertsPage` empty state copy is misleading
**Where:** `SharedAlertsPage.jsx`  
**Description:** The empty state says "Create shared alert channels in team settings to see them here." But the page itself has an "Add Shared Channel" button. The copy contradicts the UI.  
**Suggested fix:** Update copy to: "No shared channels yet. Create one using the button above."

---

### P3-10: Grid/list view toggle on Dashboard persists only in component state
**Where:** `DashboardPage.jsx`  
**Description:** The grid/list view preference resets to grid on every page load. For a tool engineers visit frequently, this is a minor but recurring annoyance.  
**Suggested fix:** Persist the preference to `localStorage`.

---

## Summary Table

| ID    | Priority | Area                        | Issue                                              |
|-------|----------|-----------------------------|----------------------------------------------------|
| P1-1  | P1       | Error handling              | `alert()`/`confirm()` used everywhere              |
| P1-2  | P1       | Engineer UX                 | New token not shown after rotation                 |
| P1-3  | P1       | Error handling              | Load failures show empty state, not error state    |
| P1-4  | P1       | Information architecture    | Shared channel silently assigned to first team     |
| P2-1  | P2       | Information architecture    | Alert channels duplicated across 3 surfaces        |
| P2-2  | P2       | Usability                   | Period/grace unit inconsistency; no grace minimum  |
| P2-3  | P2       | Usability / Bug             | Bulk actions bar always visible; `handleBulkResume` undefined |
| P2-4  | P2       | Usability                   | Alert config collapsed with no status summary      |
| P2-5  | P2       | Engineer UX                 | Ping history hard-capped at 20, no pagination      |
| P2-6  | P2       | Empty states                | "No pings yet" has no actionable next step         |
| P2-7  | P2       | Usability                   | App loading state is plain text                    |
| P2-8  | P2       | Information architecture    | No breadcrumbs or active nav state                 |
| P2-9  | P2       | Usability                   | Icon-only delete buttons, no visual separation     |
| P2-10 | P2       | Consistency                 | Debug `console.log` in production code             |
| P3-1  | P3       | Empty states                | Empty states have no embedded CTA                  |
| P3-2  | P3       | Consistency                 | "Shared Alerts" button uses non-standard icon      |
| P3-3  | P3       | Consistency                 | "Shared" badge rendered twice on channel items     |
| P3-4  | P3       | Accessibility               | Status icon has no aria-label                      |
| P3-5  | P3       | Engineer UX                 | No preset options for period/grace time            |
| P3-6  | P3       | Usability                   | Login page exposes auth provider name              |
| P3-7  | P3       | Consistency                 | Emoji icons mixed with Lucide icons                |
| P3-8  | P3       | Usability                   | No success feedback after sending member invite    |
| P3-9  | P3       | Empty states                | SharedAlertsPage empty state copy contradicts UI   |
| P3-10 | P3       | Usability                   | Grid/list preference not persisted                 |
