import React, { useCallback, useEffect, useMemo, useState } from 'react';
import * as echarts from 'echarts';
import ReactECharts from 'echarts-for-react';
import type { EChartsOption } from 'echarts';
import { ArrowLeft, Maximize2, RefreshCw, Wifi, WifiOff } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import {
  api,
  type EnterpriseDirectoryItem,
  type GovAlertItem,
  type GovStatsData,
  type RecruitmentGap,
  type RecruitmentTask,
  type WorkflowStatsData,
} from '@/src/services/api';
import { cn } from '@/src/lib/utils';

type SourceKey =
  | 'stats'
  | 'alerts'
  | 'workflows'
  | 'gaps'
  | 'tasks'
  | 'pagerank'
  | 'directory';

type SourceState = Record<SourceKey, boolean>;

type RankItem = {
  name: string;
  value: number;
};

type RegionItem = {
  name: string;
  count: number;
  x: number;
  y: number;
  product: string;
};

type RegionGeoRule = {
  provinces: string[];
  coord: [number, number];
};

type ScreenData = {
  stats: GovStatsData;
  alerts: GovAlertItem[];
  workflow: WorkflowStatsData;
  gaps: RecruitmentGap[];
  tasks: RecruitmentTask[];
  rankItems: RankItem[];
  directory: EnterpriseDirectoryItem[];
};

const SOURCE_META: Record<SourceKey, string> = {
  stats: '监管统计',
  alerts: '风险预警',
  workflows: '处置闭环',
  gaps: '招商缺口',
  tasks: '招商任务',
  pagerank: '关键节点',
  directory: '企业地区分布',
};

const EMPTY_SOURCE_STATE: SourceState = {
  stats: false,
  alerts: false,
  workflows: false,
  gaps: false,
  tasks: false,
  pagerank: false,
  directory: false,
};

const FALLBACK_STATS: GovStatsData = {
  enterprise_count: 78,
  supply_count: 814,
  demand_count: 562,
  alert_count: 8,
};

const FALLBACK_ALERTS: GovAlertItem[] = [
  {
    id: 9001,
    product_name: '高精度传感器',
    message: '核心零部件库存低于安全阈值，建议联动成渝和长三角供应商。',
    level: 'red',
    dimension: '库存',
    suggestion: '优先调度备选供应商并跟踪交付周期。',
    created_at: '2026-06-10 09:42',
  },
  {
    id: 9002,
    product_name: '工业控制主板',
    message: '近 7 日采购需求上涨，需关注交付周期。',
    level: 'yellow',
    dimension: '需求',
    suggestion: '建议扩充二级供应池。',
    created_at: '2026-06-10 09:31',
  },
  {
    id: 9003,
    product_name: '智能网关模组',
    message: '区域供应偏集中，建议补充备选供应商。',
    level: 'blue',
    dimension: '集中度',
    suggestion: '持续观察区域备份能力。',
    created_at: '2026-06-10 08:58',
  },
  {
    id: 9004,
    product_name: '伺服驱动器',
    message: '部分企业报价波动，需要持续跟踪。',
    level: 'yellow',
    dimension: '价格',
    suggestion: '纳入价格指数观察清单。',
    created_at: '2026-06-10 08:21',
  },
];

const FALLBACK_WORKFLOW: WorkflowStatsData = {
  total: 32,
  pending: 7,
  processing: 11,
  completed: 23,
  rejected: 2,
  avg_response_hours: 5.6,
  completion_rate: 0.72,
};

const FALLBACK_GAPS: RecruitmentGap[] = [
  {
    product_name: '高精度传感器',
    gap_type: 'localization_shortage',
    gap_type_label: '本地供应不足',
    supplier_count: 3,
    local_ratio: 0.18,
    urgency: 'critical',
    urgency_label: '极紧迫',
    affected_enterprises: 24,
    suggestion: {
      enterprise_type: '精密电子制造企业',
      estimated_investment: '3000 万元',
    },
  },
  {
    product_name: '工业控制主板',
    gap_type: 'supplier_shortage',
    gap_type_label: '产能缺口',
    supplier_count: 5,
    local_ratio: 0.34,
    urgency: 'high',
    urgency_label: '紧迫',
    affected_enterprises: 18,
    suggestion: {
      enterprise_type: '工控主板配套企业',
      estimated_investment: '5000 万元',
    },
  },
  {
    product_name: '智能网关模组',
    gap_type: 'graph_gap',
    gap_type_label: '图谱缺口',
    supplier_count: 7,
    local_ratio: 0.42,
    urgency: 'medium',
    urgency_label: '一般',
    affected_enterprises: 15,
  },
];

const FALLBACK_TASKS: RecruitmentTask[] = [
  {
    id: 1,
    task_name: '招商任务-高精度传感器',
    target_product: '高精度传感器',
    target_enterprise_name: null,
    target_enterprise_location: null,
    status: 'pending',
    priority: 'high',
    progress_notes: null,
    deadline: null,
    created_at: '2026-06-10 09:10',
  },
  {
    id: 2,
    task_name: '招商任务-工业控制主板',
    target_product: '工业控制主板',
    target_enterprise_name: null,
    target_enterprise_location: null,
    status: 'negotiating',
    priority: 'normal',
    progress_notes: null,
    deadline: null,
    created_at: '2026-06-10 08:50',
  },
];

const FALLBACK_RANK_ITEMS: RankItem[] = [
  { name: '工业控制主板', value: 92 },
  { name: '智能网关模组', value: 84 },
  { name: '高精度传感器', value: 78 },
  { name: '伺服驱动器', value: 66 },
];

const REGION_RULES = [
  {
    name: '京津冀',
    keywords: ['北京', '天津', '河北', '石家庄', '唐山', '保定'],
    x: 60,
    y: 31,
    ratio: 0.19,
    product: '工业控制主板',
  },
  {
    name: '长三角',
    keywords: ['上海', '江苏', '浙江', '安徽', '南京', '苏州', '杭州', '宁波', '合肥'],
    x: 68,
    y: 52,
    ratio: 0.38,
    product: '智能网关模组',
  },
  {
    name: '粤港澳',
    keywords: ['广东', '广州', '深圳', '佛山', '东莞', '香港', '澳门', '珠海'],
    x: 61,
    y: 75,
    ratio: 0.15,
    product: '高精度传感器',
  },
  {
    name: '成渝',
    keywords: ['四川', '重庆', '成都', '绵阳'],
    x: 42,
    y: 60,
    ratio: 0.12,
    product: '伺服驱动器',
  },
  {
    name: '中部枢纽',
    keywords: ['湖南', '湖北', '河南', '江西', '武汉', '长沙', '郑州', '南昌'],
    x: 55,
    y: 57,
    ratio: 0.16,
    product: '新能源配套件',
  },
] as const;

const REGION_GEO: Record<string, RegionGeoRule> = {
  京津冀: {
    provinces: ['北京', '天津', '河北'],
    coord: [116.4, 39.9],
  },
  长三角: {
    provinces: ['上海', '江苏', '浙江', '安徽'],
    coord: [120.15, 31.95],
  },
  粤港澳: {
    provinces: ['广东', '香港', '澳门'],
    coord: [113.35, 23.12],
  },
  成渝: {
    provinces: ['四川', '重庆'],
    coord: [104.07, 30.67],
  },
  中部枢纽: {
    provinces: ['湖南', '湖北', '河南', '江西'],
    coord: [113.0, 28.2],
  },
};

type EChartsWindow = Window & typeof globalThis & {
  echarts?: typeof echarts;
  __chainyipeiChinaMapReady?: boolean;
};

const EMPTY_DATA: ScreenData = {
  stats: FALLBACK_STATS,
  alerts: FALLBACK_ALERTS,
  workflow: FALLBACK_WORKFLOW,
  gaps: FALLBACK_GAPS,
  tasks: FALLBACK_TASKS,
  rankItems: FALLBACK_RANK_ITEMS,
  directory: [],
};

function pad(value: number) {
  return String(value).padStart(2, '0');
}

function formatScreenTime(date: Date) {
  return `${date.getFullYear()}年${pad(date.getMonth() + 1)}月${pad(date.getDate())}日-${pad(date.getHours())}时${pad(date.getMinutes())}分${pad(date.getSeconds())}秒`;
}

function formatSyncTime(date: Date | null) {
  if (!date) return '待同步';
  return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

function formatNumber(value: number | undefined | null) {
  if (value === undefined || value === null || Number.isNaN(value)) return '0';
  return new Intl.NumberFormat('zh-CN').format(value);
}

function levelLabel(level: string) {
  if (level === 'red') return '高危';
  if (level === 'yellow') return '中级';
  return '低级';
}

function urgencyRank(gap: RecruitmentGap) {
  const urgency = gap.urgency || gap.urgency_label || '';
  if (urgency.includes('critical') || urgency.includes('紧急') || urgency.includes('极')) return 4;
  if (urgency.includes('high') || urgency.includes('较高') || urgency.includes('紧迫')) return 3;
  if (urgency.includes('medium') || urgency.includes('一般')) return 2;
  return 1;
}

function fallbackRegions(totalEnterpriseCount: number): RegionItem[] {
  let assigned = 0;
  return REGION_RULES.map((rule, index) => {
    const isLast = index === REGION_RULES.length - 1;
    const count = isLast
      ? Math.max(totalEnterpriseCount - assigned, 0)
      : Math.max(Math.round(totalEnterpriseCount * rule.ratio), 0);
    assigned += count;
    return {
      name: rule.name,
      count,
      x: rule.x,
      y: rule.y,
      product: rule.product,
    };
  });
}

function classifyEnterpriseRegion(item: EnterpriseDirectoryItem) {
  const text = `${item.province || ''}${item.city || ''}${item.address || ''}`;
  return REGION_RULES.find((rule) => rule.keywords.some((keyword) => text.includes(keyword)))?.name;
}

function buildRegions(directory: EnterpriseDirectoryItem[], stats: GovStatsData): RegionItem[] {
  const counts = new Map<string, number>();
  REGION_RULES.forEach((rule) => counts.set(rule.name, 0));

  directory.forEach((item) => {
    const region = classifyEnterpriseRegion(item);
    if (region) counts.set(region, (counts.get(region) || 0) + 1);
  });

  const matchedTotal = [...counts.values()].reduce((sum, count) => sum + count, 0);
  if (matchedTotal <= 0) return fallbackRegions(stats.enterprise_count || FALLBACK_STATS.enterprise_count);

  return REGION_RULES.map((rule) => ({
    name: rule.name,
    count: counts.get(rule.name) || 0,
    x: rule.x,
    y: rule.y,
    product: rule.product,
  }));
}

function normalizeRankItems(value: unknown): RankItem[] {
  const payload = Array.isArray(value)
    ? value
    : typeof value === 'object' && value !== null && Array.isArray((value as { data?: unknown[] }).data)
      ? (value as { data: unknown[] }).data
      : [];

  const normalized = payload
    .map((item) => {
      if (typeof item !== 'object' || item === null) return null;
      const row = item as Record<string, unknown>;
      const name = String(row.name || row.node || row.product_name || row.label || '').trim();
      const rawValue = Number(row.score || row.value || row.rank || row.pagerank || row.degree || 0);
      if (!name) return null;
      return { name, value: Number.isFinite(rawValue) && rawValue > 0 ? rawValue : 1 };
    })
    .filter(Boolean) as RankItem[];

  return normalized.length > 0 ? normalized.slice(0, 6) : FALLBACK_RANK_ITEMS;
}

function trendValues(base: number, offset: number) {
  return Array.from({ length: 8 }, (_, index) => (
    Math.max(0, Math.round(base * (0.56 + index * 0.06 + (index % 2 === 0 ? 0.03 : -0.01)) + offset))
  ));
}

function resolveResult<T>(result: PromiseSettledResult<T>, fallback: T): T {
  return result.status === 'fulfilled' ? result.value : fallback;
}

function getSourceState(results: PromiseSettledResult<unknown>[]): SourceState {
  const keys = Object.keys(EMPTY_SOURCE_STATE) as SourceKey[];
  return keys.reduce((acc, key, index) => {
    acc[key] = results[index]?.status === 'fulfilled';
    return acc;
  }, { ...EMPTY_SOURCE_STATE });
}

function screenAssetPath(fileName: string) {
  const base = import.meta.env.BASE_URL || '/';
  return `${base.endsWith('/') ? base : `${base}/`}${fileName}`;
}

function useChinaMapReady() {
  const [ready, setReady] = useState(() => (
    typeof window !== 'undefined'
    && Boolean((window as EChartsWindow).__chainyipeiChinaMapReady)
    && Boolean(echarts.getMap?.('china'))
  ));

  useEffect(() => {
    const win = window as EChartsWindow;
    win.echarts = echarts;

    if (echarts.getMap?.('china')) {
      win.__chainyipeiChinaMapReady = true;
      setReady(true);
      return;
    }

    const existing = document.querySelector<HTMLScriptElement>('script[data-chainyipei-china-map]');
    const markReady = () => {
      win.__chainyipeiChinaMapReady = Boolean(echarts.getMap?.('china'));
      setReady(win.__chainyipeiChinaMapReady === true);
    };

    if (existing) {
      existing.addEventListener('load', markReady);
      existing.addEventListener('error', () => setReady(false));
      return () => {
        existing.removeEventListener('load', markReady);
      };
    }

    const script = document.createElement('script');
    script.src = screenAssetPath('china.js');
    script.async = true;
    script.dataset.chainyipeiChinaMap = 'true';
    script.onload = markReady;
    script.onerror = () => setReady(false);
    document.head.appendChild(script);
  }, []);

  return ready;
}

function buildProvinceMapData(regions: RegionItem[]) {
  return regions.flatMap((region) => {
    const geo = REGION_GEO[region.name];
    if (!geo) return [];
    const provinceValue = Math.max(1, Math.round(region.count / Math.max(geo.provinces.length, 1)));
    return geo.provinces.map((province) => ({
      name: province,
      value: provinceValue,
      regionName: region.name,
      product: region.product,
    }));
  });
}

function buildRegionScatterData(regions: RegionItem[]) {
  return regions
    .map((region) => {
      const geo = REGION_GEO[region.name];
      if (!geo) return null;
      return {
        name: region.name,
        value: [...geo.coord, region.count],
        product: region.product,
      };
    })
    .filter(Boolean) as Array<{ name: string; value: [number, number, number]; product: string }>;
}

function buildRegionLineData(regions: RegionItem[], topRegion: RegionItem) {
  const fromCoord = REGION_GEO[topRegion.name]?.coord;
  if (!fromCoord) return [];
  return regions
    .filter((region) => region.name !== topRegion.name && REGION_GEO[region.name])
    .map((region) => ({
      fromName: topRegion.name,
      toName: region.name,
      coords: [fromCoord, REGION_GEO[region.name].coord],
      value: region.count,
    }));
}

function buildChinaMapOption(regions: RegionItem[], topRegion: RegionItem): EChartsOption {
  const provinceData = buildProvinceMapData(regions);
  const scatterData = buildRegionScatterData(regions);
  const lineData = buildRegionLineData(regions, topRegion);
  const maxValue = Math.max(...provinceData.map((item) => Number(item.value) || 0), 1);

  return {
    ...chartBase(),
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(7, 18, 38, 0.94)',
      borderColor: 'rgba(88, 166, 255, 0.46)',
      borderWidth: 1,
      textStyle: { color: '#e5f3ff', fontSize: 12 },
      extraCssText: 'box-shadow:0 18px 42px rgba(0,0,0,.35);border-radius:6px;',
      formatter: (params: unknown) => {
        const row = params as {
          name?: string;
          data?: { product?: string; regionName?: string; value?: number | number[] };
          value?: number | number[];
          seriesType?: string;
        };
        const value = Array.isArray(row.value) ? row.value[2] : row.value;
        if (row.seriesType === 'effectScatter') {
          return `${row.name}<br/>重点产品：${row.data?.product || '-'}<br/>企业数量：${value || 0}家`;
        }
        if (row.data?.regionName) {
          return `${row.data.regionName} · ${row.name}<br/>区域产品：${row.data.product || '-'}<br/>省域企业：${row.data.value || 0}家`;
        }
        return `${row.name || '-'}<br/>暂无企业标注`;
      },
    },
    visualMap: {
      show: false,
      min: 0,
      max: maxValue,
      inRange: {
        color: ['#153a7a', '#1d6fff', '#48d6ff'],
      },
    },
    geo: {
      map: 'china',
      roam: false,
      zoom: 1.12,
      top: 46,
      bottom: 18,
      label: {
        show: true,
        color: 'rgba(216,236,255,.7)',
        fontSize: 9,
      },
      itemStyle: {
        areaColor: '#102f75',
        borderColor: 'rgba(105,215,255,.6)',
        borderWidth: 1,
        shadowColor: 'rgba(72,214,255,.28)',
        shadowBlur: 14,
      },
      emphasis: {
        label: { color: '#fff', fontWeight: 700 },
        itemStyle: { areaColor: '#1d6fff' },
      },
    },
    series: [
      {
        name: '省域企业',
        type: 'map',
        map: 'china',
        geoIndex: 0,
        data: provinceData,
      },
      {
        name: '区域企业',
        type: 'effectScatter',
        coordinateSystem: 'geo',
        zlevel: 3,
        rippleEffect: {
          brushType: 'stroke',
          scale: 5,
        },
        symbolSize: (value: unknown) => {
          const list = Array.isArray(value) ? value : [0, 0, 0];
          return Math.max(12, Math.min(28, 10 + Math.sqrt(Number(list[2]) || 1) * 2.2));
        },
        itemStyle: {
          color: '#f6d365',
          shadowBlur: 18,
          shadowColor: 'rgba(246,211,101,.55)',
        },
        label: {
          show: true,
          formatter: '{b}',
          position: 'right',
          color: '#f4faff',
          fontSize: 12,
          fontWeight: 700,
        },
        data: scatterData,
      },
      {
        name: '协同链路',
        type: 'lines',
        coordinateSystem: 'geo',
        zlevel: 2,
        effect: {
          show: true,
          period: 5,
          trailLength: 0.18,
          symbol: 'arrow',
          symbolSize: 6,
          color: '#f6d365',
        },
        lineStyle: {
          color: '#48d6ff',
          width: 1.4,
          opacity: 0.42,
          curveness: 0.24,
        },
        data: lineData,
      },
    ],
  };
}

function chartBase(): EChartsOption {
  return {
    backgroundColor: 'transparent',
    textStyle: {
      color: '#b9d8ff',
      fontFamily: 'Inter, PingFang SC, Microsoft YaHei, sans-serif',
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(7, 18, 38, 0.94)',
      borderColor: 'rgba(88, 166, 255, 0.42)',
      borderWidth: 1,
      textStyle: { color: '#e5f3ff', fontSize: 12 },
      extraCssText: 'box-shadow:0 18px 42px rgba(0,0,0,.35);border-radius:6px;',
    },
  };
}

function useNow() {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  return now;
}

export default function GovDigitalScreen() {
  const navigate = useNavigate();
  const now = useNow();
  const [data, setData] = useState<ScreenData>(EMPTY_DATA);
  const [sources, setSources] = useState<SourceState>(EMPTY_SOURCE_STATE);
  const [loading, setLoading] = useState(true);
  const [lastSync, setLastSync] = useState<Date | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    const results = await Promise.allSettled([
      api.getGovStats(),
      api.getGovAlertsList(),
      api.getWorkflowStats(),
      api.getRecruitmentGaps({ includeNeo4j: false }, { timeoutMs: 35_000 }),
      api.getRecruitmentTasks(),
      api.getGovPageRank(),
      api.fetchEnterpriseDirectory({ limit: 200 }),
    ]);

    const [
      statsResult,
      alertsResult,
      workflowResult,
      gapsResult,
      tasksResult,
      pagerankResult,
      directoryResult,
    ] = results;

    const nextStats = resolveResult(statsResult as PromiseSettledResult<GovStatsData>, FALLBACK_STATS);
    const nextAlerts = resolveResult(alertsResult as PromiseSettledResult<GovAlertItem[]>, FALLBACK_ALERTS);
    const nextWorkflow = resolveResult(workflowResult as PromiseSettledResult<WorkflowStatsData>, FALLBACK_WORKFLOW);
    const nextGapsPayload = resolveResult(
      gapsResult as PromiseSettledResult<{ success: boolean; total: number; gaps: RecruitmentGap[] }>,
      { success: false, total: FALLBACK_GAPS.length, gaps: FALLBACK_GAPS },
    );
    const nextTasksPayload = resolveResult(
      tasksResult as PromiseSettledResult<{ success: boolean; tasks: RecruitmentTask[]; total: number; page: number }>,
      { success: false, tasks: FALLBACK_TASKS, total: FALLBACK_TASKS.length, page: 1 },
    );
    const nextDirectoryPayload = resolveResult(
      directoryResult as PromiseSettledResult<{ count: number; enterprises: EnterpriseDirectoryItem[] }>,
      { count: 0, enterprises: [] },
    );

    setData({
      stats: nextStats,
      alerts: Array.isArray(nextAlerts) && nextAlerts.length > 0 ? nextAlerts : FALLBACK_ALERTS,
      workflow: nextWorkflow,
      gaps: Array.isArray(nextGapsPayload.gaps) && nextGapsPayload.gaps.length > 0 ? nextGapsPayload.gaps : FALLBACK_GAPS,
      tasks: Array.isArray(nextTasksPayload.tasks) && nextTasksPayload.tasks.length > 0 ? nextTasksPayload.tasks : FALLBACK_TASKS,
      rankItems: normalizeRankItems(pagerankResult.status === 'fulfilled' ? pagerankResult.value : []),
      directory: Array.isArray(nextDirectoryPayload.enterprises) ? nextDirectoryPayload.enterprises : [],
    });
    setSources(getSourceState(results));
    setLastSync(new Date());
    setLoading(false);
  }, []);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 120_000);
    return () => window.clearInterval(timer);
  }, [load]);

  const onlineCount = Object.values(sources).filter(Boolean).length;
  const failedSources = (Object.keys(sources) as SourceKey[])
    .filter((key) => !sources[key])
    .map((key) => SOURCE_META[key]);

  const regions = useMemo(() => buildRegions(data.directory, data.stats), [data.directory, data.stats]);
  const topRegion = regions.reduce((max, item) => (item.count > max.count ? item : max), regions[0]);
  const alertCounts = useMemo(() => {
    const counts = { red: 0, yellow: 0, blue: 0 };
    data.alerts.forEach((alert) => {
      if (alert.level === 'red') counts.red += 1;
      else if (alert.level === 'yellow') counts.yellow += 1;
      else counts.blue += 1;
    });
    return counts;
  }, [data.alerts]);
  const sortedGaps = useMemo(
    () => [...data.gaps].sort((a, b) => urgencyRank(b) - urgencyRank(a)).slice(0, 3),
    [data.gaps],
  );
  const marketTotal = data.stats.supply_count + data.stats.demand_count;
  const completionRate = Math.round((data.workflow.completion_rate || 0) * 100);
  const regionTotal = Math.max(regions.reduce((sum, region) => sum + region.count, 0), 1);
  const taskActiveCount = data.tasks.filter((task) => task.status !== 'signed').length;

  const supplyTrendOption = useMemo<EChartsOption>(() => {
    const supply = trendValues(data.stats.supply_count || FALLBACK_STATS.supply_count, 12);
    const demand = trendValues(data.stats.demand_count || FALLBACK_STATS.demand_count, -18);
    return {
      ...chartBase(),
      color: ['#2f89cf', '#00d4ff', '#f6d365'],
      legend: {
        top: 0,
        right: 8,
        itemWidth: 8,
        itemHeight: 8,
        textStyle: { color: 'rgba(214,235,255,.72)', fontSize: 10 },
      },
      grid: { left: 4, top: 30, right: 8, bottom: 2, containLabel: true },
      xAxis: {
        type: 'category',
        data: ['3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月'],
        axisTick: { show: false },
        axisLine: { show: false },
        axisLabel: { color: 'rgba(214,235,255,.68)', fontSize: 10 },
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: 'rgba(214,235,255,.54)', fontSize: 10 },
        splitLine: { lineStyle: { color: 'rgba(71, 150, 255, .14)' } },
      },
      series: [
        {
          name: '活跃供应',
          type: 'bar',
          barWidth: '28%',
          data: supply,
          itemStyle: { borderRadius: [4, 4, 0, 0] },
        },
        {
          name: '活跃采购',
          type: 'bar',
          barWidth: '28%',
          data: demand,
          itemStyle: { borderRadius: [4, 4, 0, 0] },
        },
        {
          name: '趋势预测',
          type: 'line',
          smooth: true,
          symbolSize: 5,
          data: supply.map((value, index) => Math.round((value + demand[index]) / 2)),
        },
      ],
    };
  }, [data.stats]);

  const riskOption = useMemo<EChartsOption>(() => ({
    ...chartBase(),
    color: ['#4db6ff', '#86e7ff', '#f6d365'],
    grid: { left: 6, top: 22, right: 16, bottom: 2, containLabel: true },
    xAxis: {
      type: 'category',
      data: ['高危', '中级', '低级'],
      axisTick: { show: false },
      axisLine: { show: false },
      axisLabel: { color: 'rgba(214,235,255,.72)', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: { color: 'rgba(214,235,255,.54)', fontSize: 10 },
      splitLine: { lineStyle: { color: 'rgba(71, 150, 255, .14)' } },
    },
    series: [
      {
        name: '风险等级',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 8,
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(77, 182, 255, .35)' },
              { offset: 1, color: 'rgba(77, 182, 255, 0)' },
            ],
          },
        },
        data: [alertCounts.red, alertCounts.yellow, alertCounts.blue],
      },
    ],
  }), [alertCounts]);

  const workflowOption = useMemo<EChartsOption>(() => ({
    ...chartBase(),
    color: ['#3ba4ff', '#48d6ff', '#f6d365', '#7fb7ff'],
    tooltip: { ...chartBase().tooltip, trigger: 'item' },
    legend: {
      bottom: 0,
      itemWidth: 8,
      itemHeight: 8,
      textStyle: { color: 'rgba(214,235,255,.68)', fontSize: 10 },
    },
    series: [
      {
        name: '处置闭环',
        type: 'pie',
        radius: ['48%', '70%'],
        center: ['50%', '44%'],
        avoidLabelOverlap: true,
        label: { color: '#d8ecff', formatter: '{b}\n{c}', fontSize: 10 },
        labelLine: { lineStyle: { color: 'rgba(216,236,255,.36)' } },
        data: [
          { name: '待处理', value: data.workflow.pending },
          { name: '处理中', value: data.workflow.processing },
          { name: '已完成', value: data.workflow.completed },
          { name: '退回', value: data.workflow.rejected },
        ],
      },
    ],
  }), [data.workflow]);

  const alertBarOption = useMemo<EChartsOption>(() => ({
    ...chartBase(),
    color: ['#4db6ff'],
    grid: { left: 8, top: 8, right: 6, bottom: 2, containLabel: true },
    xAxis: { show: false, type: 'value' },
    yAxis: {
      type: 'category',
      inverse: true,
      data: data.alerts.slice(0, 4).map((alert) => alert.product_name),
      axisTick: { show: false },
      axisLine: { show: false },
      axisLabel: { color: '#d8ecff', fontSize: 10, width: 82, overflow: 'truncate' },
    },
    series: [
      {
        type: 'bar',
        barWidth: 8,
        data: data.alerts.slice(0, 4).map((alert) => (
          alert.level === 'red' ? 100 : alert.level === 'yellow' ? 68 : 42
        )),
        itemStyle: {
          borderRadius: 12,
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 1,
            y2: 0,
            colorStops: [
              { offset: 0, color: '#1d6fff' },
              { offset: 1, color: '#48d6ff' },
            ],
          },
        },
        label: {
          show: true,
          position: 'right',
          color: '#b9d8ff',
          fontSize: 10,
          formatter: '{c}',
        },
      },
    ],
  }), [data.alerts]);

  const gapOption = useMemo<EChartsOption>(() => ({
    ...chartBase(),
    color: ['#48d6ff', '#f6d365'],
    legend: {
      top: 0,
      right: 6,
      itemWidth: 8,
      itemHeight: 8,
      textStyle: { color: 'rgba(214,235,255,.68)', fontSize: 10 },
    },
    grid: { left: 6, top: 28, right: 8, bottom: 2, containLabel: true },
    xAxis: {
      type: 'category',
      data: sortedGaps.map((gap) => gap.product_name),
      axisTick: { show: false },
      axisLine: { show: false },
      axisLabel: { color: 'rgba(214,235,255,.7)', fontSize: 10, width: 66, overflow: 'truncate' },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: 'rgba(214,235,255,.54)', fontSize: 10 },
      splitLine: { lineStyle: { color: 'rgba(71, 150, 255, .14)' } },
    },
    series: [
      {
        name: '影响企业',
        type: 'line',
        smooth: true,
        symbolSize: 7,
        data: sortedGaps.map((gap) => gap.affected_enterprises ?? gap.affected_enterprise_count ?? 0),
      },
      {
        name: '供应商',
        type: 'bar',
        barWidth: 12,
        data: sortedGaps.map((gap) => gap.supplier_count || 0),
        itemStyle: { borderRadius: [4, 4, 0, 0] },
      },
    ],
  }), [sortedGaps]);

  const regionOption = useMemo<EChartsOption>(() => ({
    ...chartBase(),
    color: ['#2f89cf', '#48d6ff', '#7fb7ff', '#f6d365', '#1d6fff'],
    tooltip: { ...chartBase().tooltip, trigger: 'item' },
    series: [
      {
        name: '地区分布',
        type: 'pie',
        radius: ['42%', '68%'],
        center: ['50%', '45%'],
        label: { color: '#d8ecff', formatter: '{b}\n{c}家', fontSize: 10 },
        labelLine: { lineStyle: { color: 'rgba(216,236,255,.36)' } },
        data: regions.map((region) => ({ name: region.name, value: region.count })),
      },
    ],
  }), [regions]);

  const requestFullscreen = () => {
    if (!document.fullscreenElement) {
      void document.documentElement.requestFullscreen?.();
    } else {
      void document.exitFullscreen?.();
    }
  };

  return (
    <div className="gov-digital-screen" data-testid="gov-digital-screen">
      <header>
        <div className="screen-status">
          <span className={cn('status-dot', onlineCount === Object.keys(sources).length ? 'online' : 'degraded')} />
          {onlineCount === Object.keys(sources).length ? <Wifi className="h-3.5 w-3.5" /> : <WifiOff className="h-3.5 w-3.5" />}
          <span>数据源 {onlineCount}/{Object.keys(sources).length} 在线</span>
          {loading && <span className="loading-text">同步中</span>}
        </div>

        <div className="screen-title">
          <h1>政府产业监管数字化大屏</h1>
          <p>ECHARTS-DEMO CONFIG · INDUSTRIAL SUPERVISION</p>
        </div>

        <div className="screen-actions">
          <div className="show-time">
            <span>当前时间</span>
            <strong>{formatScreenTime(now)}</strong>
          </div>
          <button type="button" onClick={() => void load()} title="刷新数据" aria-label="刷新数据">
            <RefreshCw className={cn('h-4 w-4', loading && 'animate-spin')} />
          </button>
          <button type="button" onClick={requestFullscreen} title="全屏投放" aria-label="全屏投放">
            <Maximize2 className="h-4 w-4" />
          </button>
          <button type="button" onClick={() => navigate('/gov')} title="返回监管首页" aria-label="返回监管首页">
            <ArrowLeft className="h-4 w-4" />
          </button>
        </div>
      </header>

      <section className="mainbox">
        <div className="column">
          <ScreenPanel className="bar" title="柱形图-供需趋势">
            <Chart option={supplyTrendOption} />
          </ScreenPanel>
          <ScreenPanel className="line" title="折线图-风险等级">
            <Chart option={riskOption} />
          </ScreenPanel>
          <ScreenPanel className="pie" title="饼形图-处置闭环">
            <Chart option={workflowOption} />
          </ScreenPanel>
        </div>

        <div className="column center-column">
          <div className="no">
            <div className="no-hd">
              <ul>
                <li>{formatNumber(data.stats.enterprise_count)}</li>
                <li>{formatNumber(marketTotal)}</li>
              </ul>
            </div>
            <div className="no-bd">
              <ul>
                <li>纳入监管企业</li>
                <li>供应 + 采购</li>
              </ul>
            </div>
            <div className="no-kpis">
              {[
                ['活跃供应', formatNumber(data.stats.supply_count)],
                ['活跃采购', formatNumber(data.stats.demand_count)],
                ['风险预警', formatNumber(data.stats.alert_count || data.alerts.length)],
                ['闭环完成率', `${completionRate}%`],
              ].map(([label, value]) => (
                <div key={label}>
                  <span>{label}</span>
                  <strong>{value}</strong>
                </div>
              ))}
            </div>
          </div>

          <ChinaMapStage
            regions={regions}
            topRegion={topRegion}
            rankItems={data.rankItems}
            healthIndex={Math.max(42, Math.min(96, 88 - alertCounts.red * 7 - alertCounts.yellow * 3 + completionRate * 0.12))}
          />

          <div className="screen-summary">
            <strong>监管研判：</strong>
            优先聚焦高危预警产品、本地化不足缺口和区域企业密集带，联动质量标签、招商任务和预警工单形成闭环。
            <span>最近同步：{formatSyncTime(lastSync)}</span>
          </div>
        </div>

        <div className="column">
          <ScreenPanel className="bar2" title="柱形图-活跃预警">
            <div className="split-chart">
              <div className="mini-chart">
                <Chart option={alertBarOption} />
              </div>
              <div className="alert-feed">
                {data.alerts.slice(0, 4).map((alert) => (
                  <article key={alert.id}>
                    <span>{levelLabel(alert.level)}</span>
                    <time>{alert.created_at?.slice(0, 16) || '待同步'}</time>
                    <strong>{alert.product_name}</strong>
                    <p>{alert.message}</p>
                  </article>
                ))}
              </div>
            </div>
          </ScreenPanel>

          <ScreenPanel className="line2" title="折线图-补链强链缺口">
            <div className="split-chart">
              <div className="mini-chart">
                <Chart option={gapOption} />
              </div>
              <div className="gap-list">
                {sortedGaps.slice(0, 2).map((gap) => (
                  <article key={gap.product_name}>
                    <div>
                      <strong>{gap.product_name}</strong>
                      <span>{gap.gap_type_label || gap.gap_type}</span>
                    </div>
                    <dl>
                      <div><dt>供应商</dt><dd>{gap.supplier_count || 0}</dd></div>
                      <div><dt>本地化</dt><dd>{Math.round((gap.local_ratio || 0) * 100)}%</dd></div>
                      <div><dt>影响</dt><dd>{gap.affected_enterprises ?? gap.affected_enterprise_count ?? 0}</dd></div>
                    </dl>
                  </article>
                ))}
              </div>
            </div>
          </ScreenPanel>

          <ScreenPanel className="pie2" title="饼形图-地区分布">
            <div className="split-chart">
              <div className="mini-chart">
                <Chart option={regionOption} />
              </div>
              <div className="region-rank">
                {regions.map((region) => (
                  <div key={region.name}>
                    <span>{region.name}</span>
                    <strong>{region.count}家</strong>
                    <i style={{ width: `${Math.round((region.count / regionTotal) * 100)}%` }} />
                  </div>
                ))}
                <div className="rank-box">
                  <span>关键节点排行</span>
                  {data.rankItems.slice(0, 3).map((item, index) => (
                    <p key={item.name}><b>{index + 1}</b>{item.name}</p>
                  ))}
                </div>
              </div>
            </div>
          </ScreenPanel>
        </div>
      </section>

      {failedSources.length > 0 && (
        <div className="screen-warning">
          待恢复数据源：{failedSources.join('、')}；当前使用最近可用数据与演示兜底值保障大屏展示。
        </div>
      )}
      <div className="screen-task-count">待推进招商任务 {taskActiveCount} 项</div>
    </div>
  );
}

function Chart({ option }: { option: EChartsOption }) {
  return (
    <ReactECharts
      option={option}
      notMerge
      lazyUpdate
      style={{ height: '100%', width: '100%' }}
      opts={{ renderer: 'canvas' }}
    />
  );
}

function ScreenPanel({
  className,
  title,
  children,
}: {
  className: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className={cn('panel', className)}>
      <h2>{title}</h2>
      <div className="chart">{children}</div>
      <div className="panel-footer" />
    </div>
  );
}

function ChinaMapStage({
  regions,
  topRegion,
  rankItems,
  healthIndex,
}: {
  regions: RegionItem[];
  topRegion: RegionItem;
  rankItems: RankItem[];
  healthIndex: number;
}) {
  const leadingProduct = rankItems[0]?.name || '关键产品';
  const chinaMapReady = useChinaMapReady();
  const chinaMapOption = useMemo(
    () => buildChinaMapOption(regions, topRegion),
    [regions, topRegion],
  );

  return (
    <div className="map">
      <div className="map1" />
      <div className="map2" />
      <div className="map3" />
      <div className="chart">
        <div className="map-title">
          <strong>中国区域监管态势</strong>
          <span>标注区域企业数量与重点产品</span>
        </div>

        <div className="china-map">
          {chinaMapReady ? (
            <Chart option={chinaMapOption} />
          ) : (
            <div className="map-loading">中国地图加载中</div>
          )}
        </div>

        <div className="map-health">
          <strong>{Math.round(healthIndex)}</strong>
          <span>健康指数</span>
        </div>

        <div className="map-metrics">
          <div><span>标注区域</span><strong>{regions.length}</strong></div>
          <div><span>平台企业</span><strong>{regions.reduce((sum, region) => sum + region.count, 0)}</strong></div>
        </div>

        <div className="region-cards">
          {regions.slice(0, 3).map((region) => (
            <article key={region.name}>
              <span>{region.name}</span>
              <strong>{region.product}</strong>
              <em>{region.count}家</em>
            </article>
          ))}
        </div>

        <div className="map-insight">
          <strong>监管研判</strong>
          <p>
            以中国地图标注重点区域公司数量，当前 {topRegion.name} 标注 {topRegion.count} 家，
            优先关注 {leadingProduct}。
          </p>
        </div>
      </div>
    </div>
  );
}
