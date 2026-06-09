import React from 'react';
import { Link } from 'react-router-dom';
import {
  Activity,
  ArrowRight,
  Database,
  KeyRound,
  LayoutDashboard,
  ScrollText,
  Settings2,
  ShieldAlert,
  UserCheck,
} from 'lucide-react';

const stats = [
  { icon: UserCheck, label: '待审核企业', value: '12', unit: '家', tone: 'risk' },
  { icon: Activity, label: '系统健康度', value: '98', unit: '%', tone: 'trust' },
  { icon: ShieldAlert, label: '今日拦截恶意报价', value: '45', unit: '次', tone: 'brand' },
  { icon: Database, label: 'API 接口请求量', value: '2.4', unit: 'M', tone: 'brand' },
] as const;

const actions = [
  { icon: UserCheck, label: '入驻审核', sub: '企业资质、角色与准入状态', path: '/admin/dashboard/onboarding' },
  { icon: Settings2, label: '规则配置', sub: '信用、预警与匹配权重', path: '/admin/dashboard/rules' },
  { icon: ShieldAlert, label: '风控中心', sub: '风险事件与处置闭环', path: '/admin/dashboard/risk' },
  { icon: KeyRound, label: '接口管理', sub: '外部数据源与 API 权限', path: '/admin/dashboard/api-management' },
] as const;

const auditRows = [
  ['10 分钟前', '系统管理员 Admin', '修改了企业信用分计算权重组合规则', '成功'],
  ['2 小时前', '系统管理员 Admin', '封禁了违规企业「智造科技有限公司」', '成功'],
  ['昨天 15:30', '系统管理员 Admin', '新增工商数据 API 数据源对接配置', '成功'],
] as const;

function toneClasses(tone: (typeof stats)[number]['tone']) {
  if (tone === 'risk') return 'bg-risk-soft text-risk';
  if (tone === 'trust') return 'bg-trust-soft text-trust';
  return 'bg-brand-soft text-brand';
}

export default function AdminDashboard() {
  return (
    <div className="mx-auto max-w-[1440px] space-y-5">
      <section className="panel overflow-hidden">
        <div className="grid grid-cols-1 lg:grid-cols-[1.2fr_0.8fr]">
          <div className="relative overflow-hidden bg-brand-hero p-7 text-white">
            <div className="absolute inset-0 bg-grid-fade opacity-10" />
            <div className="relative">
              <p className="mb-2 text-xs font-bold uppercase text-sidebar-text">平台管理后台</p>
              <h1 className="mb-3 text-2xl font-black">运营控制中枢</h1>
              <p className="max-w-xl text-sm leading-6 text-sidebar-text">
                汇总企业准入、风控事件、API 数据源与敏感操作日志，帮助平台管理员快速定位异常并完成治理动作。
              </p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 bg-surface p-5">
            {[
              ['规则版本', 'v2.6'],
              ['审计留痕', '开启'],
              ['API 状态', '运行中'],
              ['队列积压', '低'],
            ].map(([label, value]) => (
              <div key={label} className="rounded-md border border-border bg-surface-subtle p-4">
                <div className="text-[11px] font-semibold text-ink-muted">{label}</div>
                <div className="metric-number mt-2 text-lg font-black text-ink">{value}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {stats.map((stat) => (
          <div key={stat.label} className="card-hover p-5">
            <div className="mb-4 flex items-center justify-between">
              <div className={`flex h-9 w-9 items-center justify-center rounded-md ${toneClasses(stat.tone)}`}>
                <stat.icon className="h-4.5 w-4.5" />
              </div>
              {stat.tone === 'risk' ? (
                <span className="rounded-md bg-critical-soft px-2 py-1 text-[10px] font-bold text-critical">
                  待处理
                </span>
              ) : null}
            </div>
            <div className="text-xs font-semibold text-ink-muted">{stat.label}</div>
            <div className="metric-number mt-2 flex items-baseline gap-1 text-3xl font-black text-ink">
              {stat.value}
              <span className="text-sm font-bold text-ink-muted">{stat.unit}</span>
            </div>
          </div>
        ))}
      </section>

      <section className="grid grid-cols-1 gap-5 lg:grid-cols-[1.45fr_0.9fr]">
        <div className="panel overflow-hidden">
          <div className="panel-header flex items-center justify-between px-5 py-4">
            <div>
              <h2 className="text-base font-bold text-ink">快捷操作</h2>
              <p className="mt-1 text-xs font-medium text-ink-muted">按平台治理频次排序</p>
            </div>
          </div>
          <div className="grid grid-cols-1 gap-3 p-4 sm:grid-cols-2">
            {actions.map((action) => (
              <Link
                key={action.path}
                to={action.path}
                className="group flex items-center gap-4 rounded-md border border-border bg-surface p-4 transition-all hover:border-brand/40 hover:bg-brand-soft/35 hover:shadow-elevation-1"
              >
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-brand-soft text-brand">
                  <action.icon className="h-4.5 w-4.5" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-bold text-ink">{action.label}</div>
                  <div className="mt-1 truncate text-[11px] font-medium text-ink-muted">{action.sub}</div>
                </div>
                <ArrowRight className="h-4 w-4 text-ink-faint transition-colors group-hover:text-brand" />
              </Link>
            ))}
          </div>
        </div>

        <div className="panel overflow-hidden">
          <div className="panel-header flex items-center justify-between px-5 py-4">
            <div>
              <h2 className="text-base font-bold text-ink">数据接入状态</h2>
              <p className="mt-1 text-xs font-medium text-ink-muted">核心运行指标</p>
            </div>
            <LayoutDashboard className="h-4.5 w-4.5 text-brand" />
          </div>
          <div className="space-y-5 p-5">
            {[
              ['当前活跃企业', '140 / 150', 93],
              ['已接入数据源', '3 / 5', 60],
              ['存储容量状态', '45%', 45],
            ].map(([label, value, width]) => (
              <div key={label}>
                <div className="mb-2 flex justify-between text-xs">
                  <span className="font-semibold text-ink-muted">{label}</span>
                  <span className="metric-number font-bold text-ink">{value}</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-surface-container">
                  <div className="h-full rounded-full bg-brand" style={{ width: `${width}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="panel overflow-hidden">
        <div className="panel-header flex items-center justify-between px-5 py-4">
          <div>
            <h2 className="text-base font-bold text-ink">最近敏感操作日志</h2>
            <p className="mt-1 text-xs font-medium text-ink-muted">Recent audit logs</p>
          </div>
          <Link to="/admin/dashboard/audit" className="btn-secondary btn-sm gap-1.5">
            <ScrollText className="h-3.5 w-3.5" /> 全部日志
          </Link>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] border-collapse text-left">
            <thead className="bg-surface-subtle">
              <tr>
                {['时间', '操作人', '动作', '状态'].map((header, index) => (
                  <th
                    key={header}
                    className={`border-b border-border px-5 py-3 text-xs font-bold uppercase text-ink-muted ${index === 3 ? 'text-right' : ''}`}
                  >
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {auditRows.map(([time, actor, action, status]) => (
                <tr key={`${time}-${action}`} className="transition-colors hover:bg-surface-subtle">
                  <td className="whitespace-nowrap px-5 py-4 text-sm text-ink-muted">{time}</td>
                  <td className="whitespace-nowrap px-5 py-4 text-sm font-bold text-ink">{actor}</td>
                  <td className="px-5 py-4 text-sm text-ink-soft">{action}</td>
                  <td className="px-5 py-4 text-right">
                    <span className="rounded-md bg-trust-soft px-2.5 py-1 text-xs font-bold text-trust">
                      {status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
