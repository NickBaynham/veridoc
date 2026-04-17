import { Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "./layouts/AppLayout";
import { AccountBillingPage } from "./pages/AccountBillingPage";
import { AccountSecurityPage } from "./pages/AccountSecurityPage";
import { CollectionAnalyticsPage } from "./pages/CollectionAnalyticsPage";
import { CollectionDetailPage } from "./pages/CollectionDetailPage";
import { CollectionsPage } from "./pages/CollectionsPage";
import { KnowledgeModelDetailPage } from "./pages/KnowledgeModelDetailPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DocumentReaderPage } from "./pages/DocumentReaderPage";
import { LoginPage } from "./pages/LoginPage";
import { ReportBuilderPage } from "./pages/ReportBuilderPage";
import { SearchPage } from "./pages/SearchPage";
import { UploadPage } from "./pages/UploadPage";
import { RequireAuth } from "./routes/RequireAuth";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/library/upload" element={<UploadPage />} />
          <Route path="/documents/:id" element={<DocumentReaderPage />} />
          <Route path="/collections" element={<CollectionsPage />} />
          <Route path="/collections/:collectionId/analytics" element={<CollectionAnalyticsPage />} />
          <Route path="/collections/:collectionId" element={<CollectionDetailPage />} />
          <Route path="/models/:modelId" element={<KnowledgeModelDetailPage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/reports/new" element={<ReportBuilderPage />} />
          <Route path="/account/billing" element={<AccountBillingPage />} />
          <Route path="/account/security" element={<AccountSecurityPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
