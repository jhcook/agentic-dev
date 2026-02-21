# INFRA-051: Local Admin Dashboard

## State

ACCEPTED

## Goal Description

Create a local web-based admin dashboard within the `env -u VIRTUAL_ENV uv run agent admin` console to display project status, including active stories, pending PRs, total ADRs, and a Kanban board for story management. This will provide developers with an at-a-glance view of project activity without relying on external tools or manual data synchronization.

## Panel Review Findings

**@Architect:** The proposed solution aligns with the overall architecture and provides a valuable feature for developers. The use of local data sources and a simple web UI is appropriate. The ADR linkage is good.

**@Security:** The "localhost binding" requirement is crucial. Ensure the application only listens on the loopback address to prevent unauthorized access. Validate input to the API endpoints, even though it's local, as a general practice.

**@QA:** The manual testing plan is a good starting point, but automated tests for the API endpoints and UI components should be considered for future iterations. Pay special attention to the accuracy of the data displayed in the dashboard.

**@Docs:** The documentation requirements in the Definition of Done are minimal. Ensure the README includes instructions on how to start the admin console and access the dashboard. Also, mention the data source and update process.

**@Compliance:** The solution appears to be compliant with existing rules. No PII should be present in the logs or data displayed on the dashboard. Ensure the application adheres to any data retention policies, though this might be less relevant for locally stored data.

**@Observability:** Add logging for key events such as API requests and data loading. Consider adding metrics for dashboard load time and data update frequency.

## Targeted Refactors & Cleanups (INFRA-043)

- [ ] Convert any `console.log` statements in the new components to use a proper logging library.
- [ ] Fix formatting issues identified in `App.tsx` during navigation updates.

## Implementation Steps

### App.tsx

#### MODIFY .agent/src/web/App.tsx

- Update the navigation bar to include links to "Dashboard" and "Kanban" routes.
- Use existing Tailwind CSS classes for styling to maintain consistency.

```typescript
// Example (adjust based on existing structure)
import { BrowserRouter as Router, Route, Link, Routes } from 'react-router-dom';
import Dashboard from './components/Dashboard';
import Kanban from './components/Kanban';

function App() {
  return (
    <Router>
      <div>
        <nav>
          <ul>
            <li>
              <Link to="/">Home</Link>
            </li>
            <li>
              <Link to="/dashboard">Dashboard</Link>
            </li>
            <li>
              <Link to="/kanban">Kanban</Link>
            </li>
          </ul>
        </nav>
        <Routes>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/kanban" element={<Kanban />} />
          {/* Other routes */}
        </Routes>
      </div>
    </Router>
  );
}
```

### Dashboard Component

#### NEW .agent/src/web/components/Dashboard.tsx

- Create a new React component `Dashboard` to display the statistics widgets and active work list.
- Fetch data from the `/api/stats` and `/api/stories` endpoints.
- Use Tailwind CSS for styling the widgets and table.

```typescript
// Example
import React, { useState, useEffect } from 'react';

function Dashboard() {
  const [stats, setStats] = useState({});
  const [activeStories, setActiveStories] = useState([]);

  useEffect(() => {
    // Fetch data from API endpoints
    const fetchStats = async () => {
      const response = await fetch('/api/stats');
      const data = await response.json();
      setStats(data);
    };

    const fetchActiveStories = async () => {
      const response = await fetch('/api/stories');
      const data = await response.json();
      setActiveStories(data.filter(story => story.status === 'IN_PROGRESS'));
    };

    fetchStats();
    fetchActiveStories();
  }, []);

  return (
    <div>
      <h2>Dashboard</h2>
      <div className="flex">
        <div className="bg-gray-200 p-4 m-2">Active Stories: {stats.activeStories}</div>
        <div className="bg-gray-200 p-4 m-2">Pending PRs: {stats.pendingPRs}</div>
        <div className="bg-gray-200 p-4 m-2">Total ADRs: {stats.totalADRs}</div>
      </div>
      <h3>Active Work</h3>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Title</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {activeStories.map(story => (
            <tr key={story.id}>
              <td>{story.id}</td>
              <td>{story.title}</td>
              <td>{story.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default Dashboard;
```

### Kanban Component

#### NEW .agent/src/web/components/Kanban.tsx

- Create a new React component `Kanban` to display the Kanban board.
- Fetch data from the `/api/stories` endpoint.
- Organize stories into columns based on their status (DRAFT, IN_PROGRESS, REVIEW, COMMITTED).
- Implement drag-and-drop functionality (read-only, no updates).
- Use Tailwind CSS for styling.

```typescript
// Example
import React, { useState, useEffect } from 'react';

function Kanban() {
  const [stories, setStories] = useState([]);

  useEffect(() => {
    const fetchStories = async () => {
      const response = await fetch('/api/stories');
      const data = await response.json();
      setStories(data);
    };

    fetchStories();
  }, []);

  const columns = ['DRAFT', 'IN_PROGRESS', 'REVIEW', 'COMMITTED'];

  return (
    <div>
      <h2>Kanban Board</h2>
      <div className="flex">
        {columns.map(column => (
          <div key={column} className="w-1/4 p-4">
            <h3>{column}</h3>
            {stories
              .filter(story => story.status === column)
              .sort((a, b) => a.id.localeCompare(b.id))
              .map(story => (
                <div key={story.id} className="bg-gray-200 p-2 m-1">{story.title}</div>
              ))}
          </div>
        ))}
      </div>
    </div>
  );
}

export default Kanban;
```

### Backend API

#### MODIFY .agent/src/backend/main.py

- Add new API endpoints `/api/stories` and `/api/stats` using FastAPI.
- Implement logic to read story data from `.agent/cache/all_stories.json`.
- Implement logic to calculate statistics (active stories, pending PRs, total ADRs).

```python
# Example (adjust based on existing structure)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import json
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],  # Adjust as needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/stories")
async def get_stories():
  """Returns all stories from the local cache."""
  try:
    with open(".agent/cache/all_stories.json", "r") as f:
      stories = json.load(f)
    return stories
  except FileNotFoundError:
    return []  # Or handle the error appropriately


@app.get("/api/stats")
async def get_stats():
  """Returns project statistics."""
  try:
    with open(".agent/cache/all_stories.json", "r") as f:
      stories = json.load(f)
  except FileNotFoundError:
    stories = []

  active_stories = sum(1 for story in stories if story["status"] == "IN_PROGRESS")
  # Dummy data - Replace with real logic to fetch PRs and ADR counts
  pending_prs = 5
  total_adrs = 10

  return {
      "activeStories": active_stories,
      "pendingPRs": pending_prs,
      "totalADRs":## Implementation Steps

### 1. Backend API Implementation
- [ ] **Create Router**: Create `.agent/src/backend/routers/dashboard.py` (or similar).
- [ ] **Define Endpoints**:
  - `GET /api/stories`: Return list of stories from `.agent/cache/all_stories.json` (or fresh parse).
  - `GET /api/stats`: Return { active: int, backlog: int, adrs: int, prs: int }.
- [ ] **Wire Router**: Update `.agent/src/backend/main.py` to `include_router`.

### 2. Frontend Navigation & Shell
- [ ] **Add Lucide Icons**: Verify `lucide-react` is installed (or install it).
- [ ] **Update Layout**: Modify `.agent/src/web/components/Layout.tsx` (or `App.tsx`) to add Sidebar links for "Dashboard" (Home) and "Kanban".

### 3. Dashboard Tab Implementation
- [ ] **Create Component**: `.agent/src/web/components/Dashboard.tsx`.
- [ ] **Stats Grid**: Implement 3-4 card layout for summary stats.
- [ ] **Active Work List**: Implement a table showing `IN_PROGRESS` items.
- [ ] **Fetch Data**: Hook up `useEffect` to call `/api/stats` and `/api/stories`.

### 4. Kanban Tab Implementation
- [ ] **Create Component**: `.agent/src/web/components/Kanban.tsx`.
- [ ] **Column Layout**: Create columns for `DRAFT`, `IN_PROGRESS`, `REVIEW`, `COMMITTED`.
- [ ] **Card Rendering**: Map stories to columns.

### 5. Integration
- [ ] **Route Wiring**: Ensure buttons in Sidebar render the correct components.

## Verification Plan

### Automated Tests
- `pytest tests/test_dashboard_api.py` (New test for API endpoints).

### Manual Verification
1. Run `env -u VIRTUAL_ENV uv run agent admin start`.
2. Open `http://127.0.0.1:8080`.
3. Verify Dashboard shows non-zero stats (if stories exist).
4. Click "Kanban" tab.
5. Verify stories are sorted into correct columns.
st for the `/api/stories` endpoint to verify it returns a list of stories from the JSON file.
- [ ] Create a unit test for the `/api/stats` endpoint to verify it returns the correct statistics.
- [ ] Add an integration test to verify that the Dashboard component correctly fetches and displays data from the API endpoints.

### Manual Verification

- [x] Run `env -u VIRTUAL_ENV uv run agent admin start`.
- [x] Go to `localhost:8080` (or configured port).
- [x] Verify that the navigation bar includes "Dashboard" and "Kanban" links.
- [x] Verify that the Dashboard loads and shows the correct counts matching the local `all_stories.json` file.
- [x] Verify that the Kanban board loads and displays stories in the correct columns based on their status.
- [x] Verify the Kanban board sorts the cards by ID.

## Definition of Done

### Documentation

- [x] CHANGELOG.md updated
- [x] README.md updated to include instructions on how to access the dashboard via `env -u VIRTUAL_ENV uv run agent admin start`.
- [ ] API Documentation updated (using FastAPI's automatic documentation, verify endpoints are documented).

### Observability

- [x] Logs are structured and free of PII
- [ ] Metrics added for dashboard load time.
- [ ] Logging added for API calls, data loads, and any errors encountered.

### Testing

- [x] Unit tests passed
- [ ] Integration tests passed
