import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { DashboardPage } from "./pages/DashboardPage";
import { AconexSettingsPage } from "./pages/AconexSettingsPage";
import { GoogleSheetsPage } from "./pages/GoogleSheetsPage";
import { TrackedWorkflowsPage } from "./pages/TrackedWorkflowsPage";
import { FeedbackRulesPage } from "./pages/FeedbackRulesPage";
import { ScheduledJobsPage } from "./pages/ScheduledJobsPage";
import { RunHistoryPage } from "./pages/RunHistoryPage";
import { WorkflowDataPage } from "./pages/WorkflowDataPage";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<DashboardPage />} />
        <Route path="settings/aconex" element={<AconexSettingsPage />} />
        <Route path="settings/google-sheets" element={<GoogleSheetsPage />} />
        <Route path="tracked" element={<TrackedWorkflowsPage />} />
        <Route path="feedback-rules" element={<FeedbackRulesPage />} />
        <Route path="schedules" element={<ScheduledJobsPage />} />
        <Route path="runs" element={<RunHistoryPage />} />
        <Route path="workflows" element={<WorkflowDataPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
