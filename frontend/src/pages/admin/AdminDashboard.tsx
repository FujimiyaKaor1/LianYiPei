import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity,
  CheckCircle2,
  CircleAlert,
  ArrowRight,
  Database,
  KeyRound,
  LayoutDashboard,
  ScrollText,
  RefreshCw,
  Settings2,
  ShieldAlert,
  UserCheck,
} from 'lucide-react';
import { api, type ProductionReadinessCheck, type ProductionReadinessReport } from '@/src/services/api';
import { apiAudit, type OperationLog } from '@/src/lib/adminApi';

const stats = [
  { icon: UserCheck, label: '待审核企业', value: '—', unit: '待接入实时指标', tone: 'risk' },
  { icon: Activity, label: '系统健康度', value: '—', unit: '待接入实时指标', tone: 'trust' },
  { icon: ShieldAlert, label: '今日拦截恶意报价', value: '—', unit: '待接入实时指标', tone: 'brand' },
  { icon: Database, label: 'API 接口请求量', value: '—', unit: '待接入实时指标', tone: 'brand' },
] as const;

const actions = [
  { icon: UserCheck, label: '入驻审核', sub: '企业资质、角色与准入状态', path: '/admin/dashboard/onboarding' },
  { icon: Settings2, label: '规则配置', sub: '信用、预警与匹配权重', path: '/admin/dashboard/rules' },
  { icon: ShieldAlert, label: '风控中心', sub: '风险事件与处置闭环', path: '/admin/dashboard/risk' },
  { icon: KeyRound, label: '接口管理', sub: '外部数据源与 API 权限', path: '/admin/dashboard/api-management' },
] as const;

function toneClasses(tone: (typeof stats)[number]['tone']) {
  if (tone === 'risk') return 'bg-risk-soft text-risk';
  if (tone === 'trust') return 'bg-trust-soft text-trust';
  return 'bg-brand-soft text-brand';
}

export default function AdminDashboard() {
  const [readiness, setReadiness] = useState<ProductionReadinessReport | null>(null);
  const [readinessLoading, setReadinessLoading] = useState(true);
  const [readinessError, setReadinessError] = useState('');
  const [auditRows, setAuditRows] = useState<OperationLog[]>([]);

  const loadReadiness = async () => {
    setReadinessLoading(true);
    setReadinessError('');
    try {
      const response = await api.getProductionReadiness();
      setReadiness(response);
    } catch (error) {
      setReadinessError(error instanceof Error ? error.message : '生产就绪状态暂时无法加载');
    } finally {
      setReadinessLoading(false);
    }
  };

  useEffect(() => { void loadReadiness(); }, []);
  useEffect(() => {
    void apiAudit.list().then(response => setAuditRows(response.logs || [])).catch(() => setAuditRows([]));
  }, []);

  const checkLabels: Record<string, string> = {
    secret_key: '应用密钥', authentication: '登录鉴权', mock_api_disabled: 'Mock 接口隔离',
    database: '生产数据库', agent_schema: 'Agent 数据结构', material_antivirus: '材料病毒扫描',
    material_storage: '私有材料存储', material_encryption: '材料加密密钥', deepseek: 'DeepSeek 模型',
    econtract: '电子合同', payment: '支付接口', smtp: '邮件触达', work_wechat: '企业微信',
    business_data: '工商数据', tax_data: '税务数据', power_data: '电力数据', scheduler: '调度器', worker: '后台 Worker', explicit_approval: '询价显式审批',
  };

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

      <section className="panel overflow-hidden">
        <div className="panel-header flex flex-wrap items-center justify-between gap-3 px-5 py-4">
          <div>
            <h2 className="flex items-center gap-2 text-base font-bold text-ink">生产就绪门禁</h2>
            <p className="mt-1 text-xs font-medium text-ink-muted">只展示布尔状态，不返回密钥、密码或完整连接串</p>
          </div>
          <div className="flex items-center gap-3">
            {readiness && <span className={`rounded-md px-2.5 py-1 text-xs font-bold ${readiness.ready ? 'bg-trust-soft text-trust' : 'bg-critical-soft text-critical'}`}>
              {readiness.ready ? '可上线' : `不可上线 · ${readiness.required_failures.length} 项必需配置缺失`}
            </span>}
            <button type="button" onClick={() => void loadReadiness()} disabled={readinessLoading} className="btn-secondary btn-sm gap-1.5" aria-label="刷新生产就绪状态">
              <RefreshCw className={`h-3.5 w-3.5 ${readinessLoading ? 'animate-spin' : ''}`} />刷新
            </button>
          </div>
        </div>
        {readinessLoading && !readiness ? <p className="p-5 text-sm text-ink-muted">正在读取生产门禁…</p> : readinessError ? <div className="m-5 rounded-md bg-critical-soft px-4 py-3 text-sm text-critical">{readinessError}</div> : readiness ? <div className="p-5">
          <div className="mb-4 flex flex-wrap items-center gap-2 text-xs text-ink-muted"><span>环境：{readiness.environment}</span>{readiness.required_failures.length > 0 && <span>· 必须先处理：{readiness.required_failures.map(key => checkLabels[key] || key).join('、')}</span>}</div>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-4">
            {(Object.entries(readiness.checks) as Array<[string, ProductionReadinessCheck]>).sort(([, left], [, right]) => Number(right.required) - Number(left.required)).map(([key, check]) => <div key={key} className="flex items-center gap-3 rounded-md border border-border bg-surface-subtle px-3 py-2.5">
              {check.configured ? <CheckCircle2 className="h-4 w-4 shrink-0 text-trust" /> : <CircleAlert className={`h-4 w-4 shrink-0 ${check.required ? 'text-critical' : 'text-ink-faint'}`} />}
              <div className="min-w-0"><p className="truncate text-xs font-bold text-ink">{checkLabels[key] || key}</p><p className="mt-0.5 text-[10px] text-ink-muted">{check.configured ? '已配置' : check.required ? '必需，待配置' : '可选，未配置'} · {check.provider || 'internal'}</p></div>
            </div>)}
          </div>
        </div> : null}
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
              ['当前活跃企业', '待接入实时指标', 0],
              ['已接入数据源', '由生产就绪检查提供', 0],
              ['存储容量状态', '由存储监控提供', 0],
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
              {auditRows.map((row) => (
                <tr key={row.id} className="transition-colors hover:bg-surface-subtle">
                  <td className="whitespace-nowrap px-5 py-4 text-sm text-ink-muted">{row.created_at ? new Date(row.created_at).toLocaleString('zh-CN') : '—'}</td>
                  <td className="whitespace-nowrap px-5 py-4 text-sm font-bold text-ink">{row.user_name || `#${row.user_id}`}</td>
                  <td className="px-5 py-4 text-sm text-ink-soft">{row.operation || '—'}{row.details ? ` · ${row.details}` : ''}</td>
                  <td className="px-5 py-4 text-right">
                    <span className="rounded-md bg-trust-soft px-2.5 py-1 text-xs font-bold text-trust">
                      已记录
                    </span>
                  </td>
                </tr>
              ))}
              {auditRows.length === 0 && <tr><td colSpan={4} className="px-5 py-8 text-center text-sm text-ink-muted">暂无可展示的实时审计记录</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
