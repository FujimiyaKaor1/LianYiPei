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
import Dashboard from './pages/Dashboard';
import SalesConsole from './pages/SalesConsole';
import Matching from './pages/Matching';
import QuotePool from './pages/QuotePool';
import OrderPipeline from './pages/OrderPipeline';
import Alerts from './pages/Alerts';
import Assets from './pages/Assets';
import GroupPurchase from './pages/GroupPurchase';
import Settings from './pages/Settings';
import FulfillmentDashboard from './pages/FulfillmentDashboard';
import CapacityCalendar from './pages/CapacityCalendar';
import EnterpriseDirectory from './pages/EnterpriseDirectory';
import AlertWorkflow from './pages/AlertWorkflow';
import ContractManagement from './pages/ContractManagement';
import InvoiceManagement from './pages/InvoiceManagement';
import LogisticsMap from './pages/LogisticsMap';

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
    return <Navigate to="/" replace />;
  }
  if (user?.role === 'admin') {
    return <Navigate to="/admin/dashboard" replace />;
  }
  return <GovLayout />;
}

function RoleBasedHomeOutlet() {
  const { user, loading } = useAuth();
  if (loading) return null;
  const path = loginHomePathForRole(user?.role);
  if (path !== '/') {
    return <Navigate to={path} replace />;
  }
  return <Dashboard />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Navigate to="/" replace />} />
      <Route element={<RequireAuth />}>
        <Route path="/supervision" element={<Navigate to="/gov" replace />} />

        <Route path="/" element={<EnterpriseLayoutGuard />}>
          <Route index element={<RoleBasedHomeOutlet />} />
          <Route path="dashboard" element={<SalesConsole />} />
          <Route path="enterprise-directory" element={<EnterpriseDirectory />} />
          <Route path="matching" element={<Matching />} />
          <Route path="collaboration" element={<Navigate to="/" replace />} />
          <Route path="analytics" element={<SalesConsole />} />
          <Route path="sales-console" element={<SalesConsole />} />
          <Route path="risk" element={<Alerts />} />
          <Route path="alerts" element={<Navigate to="/risk" replace />} />
          <Route path="orders" element={<OrderPipeline />} />
          <Route path="favorites" element={<Navigate to="/sales-console" replace />} />
          <Route path="assets" element={<Assets />} />
          <Route path="settings" element={<Settings />} />
          <Route path="group-purchase" element={<GroupPurchase />} />
          <Route path="quote-pool" element={<QuotePool />} />
          <Route path="fulfillment" element={<FulfillmentDashboard />} />
          <Route path="capacity-calendar" element={<CapacityCalendar />} />
          <Route path="alert-workflow" element={<AlertWorkflow />} />
          <Route path="contracts" element={<ContractManagement />} />
          <Route path="invoice" element={<InvoiceManagement />} />
          <Route path="logistics" element={<LogisticsMap />} />
          <Route path="data-auth" element={<Navigate to="/settings" replace />} />
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
          </Route>
        </Route>

        <Route path="/admin" element={<Navigate to="/admin/dashboard" replace />} />

        <Route path="*" element={
          <div className="min-h-screen flex flex-col items-center justify-center bg-[#F5F5F7] text-neutral-500">
            <p className="text-6xl font-bold text-neutral-200 mb-4">404</p>
            <p className="text-sm mb-6">页面未找到</p>
            <a href="/" className="text-sm text-blue-500 hover:underline">返回首页</a>
          </div>
        } />
      </Route>
    </Routes>
  );
}
