/**
 * 政府端：Neo4j 全平台产业链关系图（ECharts force graph）
 */
import React, { useCallback, useEffect, useMemo, useState, useRef } from 'react';
import ReactECharts from 'echarts-for-react';
import { Loader2, AlertCircle, RefreshCw, ZoomIn, MousePointer2, Network } from 'lucide-react';
import { cn } from '@/src/lib/utils';
import { api } from '@/src/services/api';
import { useTheme } from '@/src/context/ThemeContext';

type GraphNode = { name: string; category?: string };
type GraphLink = { source: string; target: string };
type PreparedGraph = {
  nodes: GraphNode[];
  links: GraphLink[];
  degreeMap: Map<string, number>;
  sourceNodeCount: number;
  sourceLinkCount: number;
  isSampled: boolean;
};

interface GovSupplyChainGraphProps {
  height: number;
  compact?: boolean;
  className?: string;
}

const LIGHT_CATEGORY_COLORS = [
  '#2F7CF6', '#2DD4BF', '#F59E0B', '#8B5CF6',
  '#0EA5E9', '#10B981', '#EF4444', '#64748B',
];

const DARK_CATEGORY_COLORS = [
  '#60A5FA', '#2DD4BF', '#FB923C', '#2563EB',
  '#F43F5E', '#34D399', '#38BDF8', '#FACC15',
];

const GRAPH_LIMITS = {
  compact: {
    requestNodes: 180,
    requestLinks: 360,
    renderNodes: 110,
    renderLinks: 260,
  },
  full: {
    requestNodes: 360,
    requestLinks: 900,
    renderNodes: 260,
    renderLinks: 650,
  },
};

const normalizeName = (value: unknown) => String(value ?? '').trim();

export function GovSupplyChainGraph({ height, compact, className }: GovSupplyChainGraphProps) {
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [links, setLinks] = useState<GraphLink[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const chartRef = useRef<ReactECharts>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const limits = compact ? GRAPH_LIMITS.compact : GRAPH_LIMITS.full;
      const res = await api.getGovGraphData(
        { max_nodes: limits.requestNodes, max_links: limits.requestLinks },
        { timeoutMs: compact ? 18_000 : 45_000 },
      );
      if (res.error) setError(String(res.error));
      setNodes((res.nodes || []) as GraphNode[]);
      setLinks((res.links || []) as GraphLink[]);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '加载失败');
      setNodes([]);
      setLinks([]);
    } finally {
      setLoading(false);
    }
  }, [compact]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    chartRef.current?.getEchartsInstance()?.resize();
  }, [theme, height]);

  const preparedGraph = useMemo<PreparedGraph>(() => {
    const normalizedNodes = nodes
      .map((node) => ({
        ...node,
        name: normalizeName(node.name),
        category: normalizeName(node.category) || '未分类',
      }))
      .filter((node) => node.name);
    const nodeByName = new Map(normalizedNodes.map((node) => [node.name, node]));

    const normalizedLinks = links
      .map((link) => ({
        source: normalizeName(link.source),
        target: normalizeName(link.target),
      }))
      .filter((link) => (
        link.source &&
        link.target &&
        link.source !== link.target &&
        nodeByName.has(link.source) &&
        nodeByName.has(link.target)
      ));

    const degreeMap = new Map<string, number>();
    normalizedLinks.forEach((link) => {
      degreeMap.set(link.source, (degreeMap.get(link.source) || 0) + 1);
      degreeMap.set(link.target, (degreeMap.get(link.target) || 0) + 1);
    });

    const limits = compact ? GRAPH_LIMITS.compact : GRAPH_LIMITS.full;
    const selectedNodes = normalizedNodes.length > limits.renderNodes
      ? [...normalizedNodes]
          .sort((a, b) => (
            (degreeMap.get(b.name) || 0) - (degreeMap.get(a.name) || 0) ||
            a.name.localeCompare(b.name, 'zh-CN')
          ))
          .slice(0, limits.renderNodes)
      : normalizedNodes;
    const selectedNames = new Set(selectedNodes.map((node) => node.name));

    const selectedLinks = normalizedLinks
      .filter((link) => selectedNames.has(link.source) && selectedNames.has(link.target))
      .sort((a, b) => (
        ((degreeMap.get(b.source) || 0) + (degreeMap.get(b.target) || 0)) -
        ((degreeMap.get(a.source) || 0) + (degreeMap.get(a.target) || 0))
      ))
      .slice(0, limits.renderLinks);

    return {
      nodes: selectedNodes,
      links: selectedLinks,
      degreeMap,
      sourceNodeCount: normalizedNodes.length,
      sourceLinkCount: normalizedLinks.length,
      isSampled: selectedNodes.length < normalizedNodes.length || selectedLinks.length < normalizedLinks.length,
    };
  }, [nodes, links, compact]);

  const option = useMemo(() => {
    if (!preparedGraph.nodes.length) return null;

    const palette = isDark ? DARK_CATEGORY_COLORS : LIGHT_CATEGORY_COLORS;
    const catSet = new Set<string>();
    preparedGraph.nodes.forEach((n) => catSet.add((n.category || '未分类').trim() || '未分类'));
    const categories = [...catSet].map((name, idx) => ({
      name,
      itemStyle: {
        color: palette[idx % palette.length],
      },
    }));
    const nameToCatIndex = new Map(categories.map((c, i) => [c.name, i]));
    const showLabels = !compact && preparedGraph.nodes.length <= 120;
    const richEffects = preparedGraph.nodes.length <= (compact ? 90 : 140);
    const compactLabel = (value: unknown) => {
      const name = String(value ?? '');
      return name.length > 7 ? `${name.slice(0, 7)}…` : name;
    };

    const graphData = preparedGraph.nodes.map((n) => {
      const cn = (n.category || '未分类').trim() || '未分类';
      const catIdx = nameToCatIndex.get(cn) ?? 0;
      const degree = preparedGraph.degreeMap.get(n.name) || 1;
      const symbolSize = compact
        ? Math.min(24, 14 + Math.log1p(degree) * 5)
        : Math.min(38, 20 + Math.log1p(degree) * 7);
      return {
        name: n.name,
        category: catIdx,
        value: degree,
        symbolSize,
        label: {
          show: showLabels,
          formatter: compact ? (params: { name?: unknown }) => compactLabel(params.name) : undefined,
          overflow: compact ? 'truncate' : undefined,
          width: compact ? 72 : undefined,
          fontSize: compact ? 10 : 12,
          color: isDark ? '#F7F8FF' : '#1E293B',
          fontWeight: 500,
          backgroundColor: isDark ? 'rgba(22,25,34,0.84)' : 'rgba(255,255,255,0.86)',
          padding: [2, 6],
          borderRadius: 4,
        },
        itemStyle: {
          borderColor: isDark ? 'rgba(255,255,255,0.16)' : 'rgba(255,255,255,0.82)',
          borderWidth: 1,
          shadowBlur: richEffects ? (compact ? 8 : 12) : 0,
          shadowColor: `${palette[catIdx % palette.length]}4D`,
        },
      };
    });

    return {
      backgroundColor: 'transparent',
      animation: compact && preparedGraph.nodes.length <= 90,
      animationDurationUpdate: compact ? 160 : 0,
      animationEasingUpdate: 'cubicOut',
      tooltip: {
        backgroundColor: isDark ? '#181B25' : '#FFFFFF',
        borderColor: isDark ? 'rgba(148,163,184,0.22)' : '#E5E7EB',
        borderWidth: 1,
        borderRadius: 8,
        padding: [10, 14],
        extraCssText: `box-shadow:${isDark ? '0 18px 46px rgba(0,0,0,.42)' : '0 18px 46px rgba(47,124,246,.14)'}`,
        textStyle: { color: isDark ? '#F7F8FF' : '#1E293B', fontSize: 12 },
        formatter: (params: any) => {
          if (params.dataType === 'edge') {
            return `<div style="font-weight:700;color:${isDark ? '#9BA3B5' : '#64748B'};font-size:11px">供应关系</div>
              <div style="margin-top:4px"><span style="color:${palette[0]};font-weight:700">${params.data.source}</span> → <span style="color:${palette[1]};font-weight:700">${params.data.target}</span></div>`;
          }
          const cat = categories[params.data.category]?.name ?? '';
          return `<div style="font-weight:700;font-size:13px;color:${isDark ? '#FFFFFF' : '#0F172A'}">${params.name}</div>
            <div style="margin-top:4px;font-size:11px;color:${isDark ? '#9BA3B5' : '#64748B'}">分类: ${cat} · 连接度 ${params.data.value ?? 1}</div>`;
        },
      },
      legend: compact
        ? undefined
        : {
            data: categories.map((c) => c.name),
            type: 'scroll',
            bottom: 4,
            left: 'center',
            textStyle: { fontSize: 11, color: isDark ? '#9BA3B5' : '#64748B' },
            itemWidth: 10,
            itemHeight: 10,
            itemGap: 16,
            icon: 'circle',
            pageTextStyle: { color: isDark ? '#9BA3B5' : '#64748B' },
          },
      series: [
        {
          type: 'graph',
          layout: 'force',
          left: compact ? '12%' : '6%',
          right: compact ? '12%' : '6%',
          top: compact ? '18%' : '12%',
          bottom: compact ? '16%' : '12%',
          roam: true,
          draggable: preparedGraph.nodes.length <= 260,
          data: graphData,
          links: preparedGraph.links.map((l) => ({
            source: l.source,
            target: l.target,
          })),
          categories,
          force: {
            repulsion: compact ? 96 : 190,
            edgeLength: compact ? 38 : 64,
            gravity: compact ? 0.11 : 0.065,
            layoutAnimation: compact && preparedGraph.nodes.length <= 90,
          },
          lineStyle: {
            color: isDark ? 'rgba(148,163,184,0.2)' : 'rgba(100,116,139,0.22)',
            width: compact ? 0.7 : 0.9,
            curveness: compact ? 0.08 : 0.14,
            opacity: richEffects ? 0.72 : 0.55,
          },
          emphasis: {
            focus: 'adjacency',
            lineStyle: { width: 2.5, color: palette[0], opacity: 1 },
            itemStyle: { shadowBlur: richEffects ? 18 : 8, shadowColor: `${palette[0]}66` },
            label: {
              fontSize: compact ? 11 : 14,
              fontWeight: 700,
              formatter: compact ? (params: { name?: unknown }) => compactLabel(params.name) : undefined,
              overflow: compact ? 'truncate' : undefined,
              width: compact ? 84 : undefined,
            },
          },
          label: {
            color: isDark ? '#F7F8FF' : '#1E293B',
            fontSize: 11,
            fontWeight: 500,
            backgroundColor: isDark ? 'rgba(22,25,34,0.84)' : 'rgba(255,255,255,0.86)',
            padding: [2, 8],
            borderRadius: 6,
            formatter: compact ? (params: { name?: unknown }) => compactLabel(params.name) : undefined,
            overflow: compact ? 'truncate' : undefined,
            width: compact ? 72 : undefined,
          },
          scaleLimit: { min: 0.2, max: 4 },
        },
      ],
    };
  }, [preparedGraph, compact, isDark]);

  /* ── loading ── */
  if (loading) {
    return (
      <div
        className={cn(
          'panel flex flex-col items-center justify-center',
          className,
        )}
        style={{ height }}
      >
        <div className="relative">
          <div className="absolute inset-0 animate-ping rounded-full border-4 border-brand-soft opacity-40" />
          <Loader2 className="relative h-8 w-8 animate-spin text-brand" />
        </div>
        <p className="mt-4 text-sm font-semibold text-ink">正在加载产业链数据...</p>
        <p className="mt-1 text-[11px] text-ink-muted">从 Neo4j 图谱中获取节点与关系</p>
      </div>
    );
  }

  /* ── error ── */
  if (error && !nodes.length) {
    return (
      <div
        className={cn(
          'panel flex flex-col items-center justify-center gap-4 p-8',
          className,
        )}
        style={{ height }}
      >
        <div className="rounded-md bg-critical-soft p-4">
          <AlertCircle className="h-10 w-10 text-critical" />
        </div>
        <div className="text-center">
          <p className="text-sm font-semibold text-ink">图谱数据加载失败</p>
          <p className="mt-1 text-xs text-ink-muted">{error}</p>
          <p className="mt-2 text-[11px] text-ink-muted">请确认 Neo4j 已启动且账号配置正确</p>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          className="btn-primary btn-sm gap-2"
        >
          <RefreshCw className="h-3.5 w-3.5" /> 重新加载
        </button>
      </div>
    );
  }

  /* ── empty ── */
  if (!nodes.length) {
    return (
      <div
        className={cn(
          'panel flex flex-col items-center justify-center gap-3 border-dashed',
          className,
        )}
        style={{ height }}
      >
        <div className="rounded-md bg-brand-soft p-3">
          <Network className="h-8 w-8 text-brand" />
        </div>
        <p className="text-sm font-semibold text-ink-muted">暂无图谱数据</p>
        <p className="text-xs text-ink-muted">Neo4j 中尚无 Product 节点或关系</p>
        <button
          type="button"
          onClick={() => void load()}
          className="btn-secondary btn-sm mt-2 gap-1.5"
        >
          <RefreshCw className="h-3 w-3" /> 刷新
        </button>
      </div>
    );
  }

  if (!preparedGraph.nodes.length) {
    return (
      <div
        className={cn(
          'panel flex flex-col items-center justify-center gap-3 p-8 text-center',
          className,
        )}
        style={{ height }}
      >
        <div className="rounded-md bg-brand-soft p-3">
          <Network className="h-8 w-8 text-brand" />
        </div>
        <p className="text-sm font-semibold text-ink">图谱数据暂不可展示</p>
        <p className="max-w-sm text-xs text-ink-muted">
          当前返回的节点或关系缺少可匹配名称，请刷新后重试。
        </p>
        <button
          type="button"
          onClick={() => void load()}
          className="btn-secondary btn-sm mt-2 gap-1.5"
        >
          <RefreshCw className="h-3 w-3" /> 刷新
        </button>
      </div>
    );
  }

  return (
    <div className={cn('panel relative overflow-hidden', className)}>
      <div className="absolute left-4 top-3 z-10 flex max-w-[calc(100%-2rem)] flex-wrap items-center gap-2">
        <span className="flex items-center gap-1.5 rounded-md border border-border bg-surface/88 px-3 py-1.5 text-[10px] font-bold text-ink shadow-elevation-1 backdrop-blur">
          <Network className="h-3.5 w-3.5 text-brand" />
          {compact ? '采样预览' : 'Neo4j 力导向图'}
        </span>
        <span className="flex items-center gap-1 rounded-md border border-border bg-surface/88 px-2.5 py-1.5 text-[10px] font-semibold text-ink-muted shadow-elevation-1 backdrop-blur">
          <MousePointer2 className="h-3 w-3" /> 拖拽节点
        </span>
        <span className="flex items-center gap-1 rounded-md border border-border bg-surface/88 px-2.5 py-1.5 text-[10px] font-semibold text-ink-muted shadow-elevation-1 backdrop-blur">
          <ZoomIn className="h-3 w-3" /> 滚轮缩放
        </span>
        <button
          type="button"
          onClick={() => void load()}
          className="flex h-7 w-7 items-center justify-center rounded-md border border-border bg-surface/88 text-ink-muted shadow-elevation-1 backdrop-blur transition-colors hover:text-brand"
          title="刷新图谱"
        >
          <RefreshCw className="h-3.5 w-3.5" />
        </button>
      </div>

      {error && (
        <div className="absolute right-3 top-3 z-10 flex max-w-[260px] items-start gap-2 rounded-md border border-risk/20 bg-risk-soft/90 px-3 py-2 text-[11px] text-risk shadow-elevation-1 backdrop-blur">
          <AlertCircle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {preparedGraph.nodes.length > 0 && (
        <div className="absolute bottom-4 right-4 z-10 rounded-md border border-border bg-surface/88 px-3 py-1.5 text-[10px] font-semibold text-ink-muted shadow-elevation-1 backdrop-blur">
          {preparedGraph.isSampled
            ? `显示 ${preparedGraph.nodes.length}/${preparedGraph.sourceNodeCount} 节点 · ${preparedGraph.links.length}/${preparedGraph.sourceLinkCount} 关系`
            : `${preparedGraph.nodes.length} 节点 · ${preparedGraph.links.length} 关系`}
        </div>
      )}

      <ReactECharts
        ref={chartRef}
        option={option!}
        style={{ height, width: '100%' }}
        opts={{ renderer: 'canvas' }}
        notMerge={false}
        lazyUpdate
      />
    </div>
  );
}
