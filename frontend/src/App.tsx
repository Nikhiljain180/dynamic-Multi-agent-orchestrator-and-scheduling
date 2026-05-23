import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout';
import AgentsPage from './pages/AgentsPage';
import HistoryPage from './pages/HistoryPage';
import MonitorPage from './pages/MonitorPage';
import SchedulesPage from './pages/SchedulesPage';
import WorkflowsPage from './pages/WorkflowsPage';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<AgentsPage />} />
          <Route path="workflows" element={<WorkflowsPage />} />
          <Route path="schedules" element={<SchedulesPage />} />
          <Route path="monitor" element={<MonitorPage />} />
          <Route path="history" element={<HistoryPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
