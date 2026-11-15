import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { useAuth } from "./lib/auth";
import Login from "./pages/Login";
import { Skeleton } from "./components/ui";

// Heavier pages are split into their own chunks.
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Ask = lazy(() => import("./pages/Ask"));
const Documents = lazy(() => import("./pages/Documents"));
const DocumentView = lazy(() => import("./pages/DocumentView"));
const Compare = lazy(() => import("./pages/Compare"));
const SearchPage = lazy(() => import("./pages/SearchPage"));
const Analytics = lazy(() => import("./pages/Analytics"));
const Resources = lazy(() => import("./pages/Resources"));
const Timeline = lazy(() => import("./pages/Timeline"));
const Saved = lazy(() => import("./pages/Saved"));
const Admin = lazy(() => import("./pages/Admin"));

export default function App() {
  const { user, loading, can } = useAuth();
  if (loading) return <div className="grid h-full place-items-center"><Skeleton className="h-10 w-48" /></div>;
  if (!user) return <Login />;

  return (
    <Layout>
      <Suspense fallback={<div className="space-y-3"><Skeleton className="h-8 w-64" /><Skeleton className="h-64 w-full" /></div>}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/ask" element={<Ask />} />
          <Route path="/documents" element={<Documents />} />
          <Route path="/documents/:id" element={<DocumentView />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/saved" element={<Saved />} />
          <Route path="/timeline" element={<Timeline />} />
          <Route path="/resources" element={<Resources />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/analytics" element={can("ADMIN") ? <Analytics /> : <Navigate to="/" replace />} />
          <Route path="/admin" element={can("ADMIN") ? <Admin /> : <Navigate to="/" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </Layout>
  );
}
