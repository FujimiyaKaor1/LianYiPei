/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { Suspense, lazy } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from './components/Layout';
import { GovLayout } from './components/GovLayout';
import { AdminLayout } from './components/AdminLayout';
import { RequireAuth } from './components/RequireAuth';
import { RequireRole } from './components/RequireRole';
import { useAuth } from './context/AuthContext';
import { loginHomePathForRole } from './lib/rbac';

// Enterprise pages
const Dashboard = lazy(() => import('./pages/Dashboard'));
const SalesConsole = lazy(() => import('./pages/SalesConsole'));
const Matching = lazy(() => import('./pages/Matching'));
const OrderPipeline = lazy(() => import('./pages/OrderPipeline'));
const Alerts = lazy(() => import('./pages/Alerts'));
const Assets = lazy(() => import('./pages/Assets'));
const GroupPurchase = lazy(() => import('./pages/GroupPurchase'));
const Settings = lazy(() => import('./pages/Settings'));
const FulfillmentDashboard = lazy(() => import('./pages/FulfillmentDashboard'));
const CapacityCalendar = lazy(() => import('./pages/CapacityCalendar'));
const EnterpriseDirectory = lazy(() => import('./pages/EnterpriseDirectory'));
const AlertWorkflow = lazy(() => import('./pages/AlertWorkflow'));
const PublicHome = lazy(() => import('./pages/PublicHome'));
const IndustryNews = lazy(() => import('./pages/IndustryNews'));
const PublicSearch = lazy(() => import('./pages/PublicSearch'));
const PublicAia = lazy(() => import('./pages/PublicAia'));
const FactoryDetail = lazy(() => import('./pages/FactoryDetail'));
const AgentMarket = lazy(() => import('./pages/AgentMarket'));
const IndustryNewsDetail = lazy(() => import('./pages/IndustryNewsDetail'));
const IndiseaHome = lazy(() => import('./indisea/App'));
import NewsManagementPage from './pages/admin/NewsManagementPage';

// Government pages
import GovDashboard from './pages/gov/GovDashboard';
import GovAlerts from './pages/gov/GovAlerts';
import GovRecruitment from './pages/gov/GovRecruitment';
import GovQualityLabels from './pages/gov/GovQualityLabels';
import GovSupplyChain from './pages/gov/GovSupplyChain';
const GovDigitalScreen = lazy(() => import('./pages/gov/GovDigitalScreen'));

// Admin pages（按需加载，减小首包）
const AdminDashboard = lazy(() => import('./pages/admin/AdminDashboard'));
const DashboardPage = lazy(() => import('./pages/admin/DashboardPage'));
const VerificationPage = lazy(() => import('./pages/admin/VerificationPage'));
const RuleConfigPage = lazy(() => import('./pages/admin/RuleConfigPage'));
const RiskCenterPage = lazy(() => import('./pages/admin/RiskCenterPage'));
const APIGatewayPage = lazy(() => import('./pages/admin/APIGatewayPage'));
const AuditLogPage = lazy(() => import('./pages/admin/AuditLogPage'));

function AuthLoadingShell() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[#F5F5F7] text-neutral-500 text-sm">
      加载中…
    </div>
  );
}

function EnterpriseLayoutGuard() {
  const { user, loading } = useAuth();
  if (loading) return <AuthLoadingShell />;
  if (user?.role === 'government') {
    return <Navigate to="/gov" replace />;
  }
  if (user?.role === 'admin') {
    return <Navigate to="/admin/dashboard" replace />;
  }
  return <Layout />;
}

function GovLayoutGuard() {
  const { user, loading } = useAuth();
  if (loading) return <AuthLoadingShell />;
  if (user?.role === 'enterprise') {
    return <Navigate to="/dashboard" replace />;
  }
  if (user?.role === 'admin') {
    return <Navigate to="/admin/dashboard" replace />;
  }
  return <GovLayout />;
}

function PublicOrRoleHome() {
  const { user, loading } = useAuth();

  if (loading) return <AuthLoadingShell />;
  if (!user) return <Navigate to="/indisea/" replace />;
  return <Navigate to={loginHomePathForRole(user.role)} replace />;
}

export default function App() {
  return (
    <Suspense fallback={<AuthLoadingShell />}>
    <Routes>
      <Route path="/" element={<PublicOrRoleHome />} />
      <Route path="/indisea/*" element={<IndiseaHome />} />
      <Route path="/indesea/*" element={<Navigate to="/indisea/" replace />} />
      <Route path="/aisearch/*" element={<PublicHome />} />
      <Route path="/login" element={<Navigate to="/aisearch/" replace />} />
      <Route path="/search" element={<PublicSearch />} />
      <Route path="/aia" element={<PublicAia />} />
      <Route path="/industry-news/:slug" element={<IndustryNewsDetail />} />
      <Route path="/industry-news" element={<IndustryNews />} />
      <Route path="/agent-market" element={<AgentMarket />} />
      <Route path="/factory/:id" element={<FactoryDetail />} />
      <Route path="/enterprise-directory" element={<PublicSearch />} />

      <Route path="/supervision" element={<Navigate to="/gov" replace />} />

      <Route element={<EnterpriseLayoutGuard />}>
        <Route path="workspace/enterprise-directory" element={<EnterpriseDirectory />} />
        <Route path="matching" element={<Matching />} />

        <Route element={<RequireAuth />}>
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="collaboration" element={<Navigate to="/dashboard" replace />} />
          <Route path="analytics" element={<SalesConsole />} />
          <Route path="sales-console" element={<SalesConsole />} />
          <Route path="risk" element={<Alerts />} />
          <Route path="alerts" element={<Navigate to="/risk" replace />} />
          <Route path="orders" element={<OrderPipeline />} />
          <Route path="favorites" element={<Navigate to="/matching?panel=favorites" replace />} />
          <Route path="assets" element={<Assets />} />
          <Route path="settings" element={<Settings />} />
          <Route path="group-purchase" element={<GroupPurchase />} />
          <Route path="quote-pool" element={<Navigate to="/matching?panel=quotes" replace />} />
          <Route path="fulfillment" element={<FulfillmentDashboard />} />
          <Route path="capacity-calendar" element={<CapacityCalendar />} />
          <Route path="alert-workflow" element={<AlertWorkflow />} />
          <Route path="data-auth" element={<Navigate to="/settings" replace />} />
        </Route>
      </Route>

      <Route element={<RequireRole allow={['government', 'admin']} />}>
        <Route
          path="/gov/screen"
          element={
            <Suspense fallback={<AuthLoadingShell />}>
              <GovDigitalScreen />
            </Suspense>
          }
        />
        <Route path="/gov" element={<GovLayoutGuard />}>
          <Route index element={<GovDashboard />} />
          <Route path="alerts" element={<GovAlerts />} />
          <Route path="supply-chain" element={<GovSupplyChain />} />
          <Route path="recruitment" element={<GovRecruitment />} />
          <Route path="labels" element={<GovQualityLabels />} />
        </Route>
      </Route>

      <Route element={<RequireRole allow={['admin']} />}>
        <Route
          path="/admin/dashboard"
          element={
            <Suspense fallback={<AuthLoadingShell />}>
              <AdminLayout />
            </Suspense>
          }
        >
          <Route index element={<AdminDashboard />} />
          <Route path="overview" element={<DashboardPage />} />
          <Route path="onboarding" element={<VerificationPage />} />
          <Route path="rules" element={<RuleConfigPage />} />
          <Route path="risk" element={<RiskCenterPage />} />
          <Route path="api-management" element={<APIGatewayPage />} />
          <Route path="audit" element={<AuditLogPage />} />
          <Route path="news" element={<NewsManagementPage />} />
        </Route>
      </Route>

      <Route path="/admin" element={<Navigate to="/admin/dashboard" replace />} />

      <Route path="*" element={
        <div className="min-h-screen flex flex-col items-center justify-center bg-[#F5F5F7] text-neutral-500">
          <p className="text-6xl font-bold text-neutral-200 mb-4">404</p>
          <p className="text-sm mb-6">页面未找到</p>
          <a href="/aisearch/" className="text-sm text-blue-500 hover:underline">返回首页</a>
        </div>
      } />
    </Routes>
    </Suspense>
  );
}
