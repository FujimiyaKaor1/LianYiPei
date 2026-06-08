/**
 * 政府端：Neo4j 全平台产业链关系图（ECharts force graph）
 * 蓝白主题美化版
 */
import React, { useCallback, useEffect, useMemo, useState, useRef } from 'react';
import ReactECharts from 'echarts-for-react';
import { Loader2, AlertCircle, RefreshCw, ZoomIn, MousePointer2 } from 'lucide-react';
import { cn } from '@/src/lib/utils';
import { api } from '@/src/services/api';

type GraphNode = { name: string; category?: string };
type GraphLink = { source: string; target: string };

interface GovSupplyChainGraphProps {
  height: number;
  compact?: boolean;
  className?: string;
}

/** 蓝白主题分类色板 */
const CATEGORY_COLORS = [
  '#1A56DB', '#2563EB', '#3B82F6', '#60A5FA',
  '#1D4ED8', '#2563EB', '#3B82F6', '#60A5FA',
  '#1E40AF', '#3B82F6', '#60A5FA', '#93C5FD',
  '#1A56DB', '#4F8FF7', '#6AA4F8', '#8AB8FA',
];

export function GovSupplyChainGraph({ height, compact, className }: GovSupplyChainGraphProps) {
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [links, setLinks] = useState<GraphLink[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const chartRef = useRef<ReactECharts>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const max_nodes = compact ? 320 : 900;
      const max_links = compact ? 900 : 4500;
      const res = await api.getGovGraphData(
        { max_nodes, max_links },
        { timeoutMs: compact ? 25_000 : 90_000 },
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

  const option = useMemo(() => {
    if (!nodes.length) return null;

    const catSet = new Set<string>();
    nodes.forEach((n) => catSet.add((n.category || '未分类').trim() || '未分类'));
    const categories = [...catSet].map((name, idx) => ({
      name,
      itemStyle: {
        color: CATEGORY_COLORS[idx % CATEGORY_COLORS.length],
      },
    }));
    const nameToCatIndex = new Map(categories.map((c, i) => [c.name, i]));
    const showLabels = !compact || nodes.length <= 72;

    const graphData = nodes.map((n) => {
      const cn = (n.category || '未分类').trim() || '未分类';
      const catIdx = nameToCatIndex.get(cn) ?? 0;
      return {
        name: n.name,
        category: catIdx,
        symbolSize: compact ? 18 : 28,
        label: {
          show: showLabels,
          fontSize: compact ? 10 : 12,
          color: '#1e293b',
          fontWeight: 500,
          backgroundColor: 'rgba(255,255,255,0.85)',
          padding: [2, 6],
          borderRadius: 4,
        },
        itemStyle: {
          shadowBlur: 12,
          shadowColor: CATEGORY_COLORS[catIdx % CATEGORY_COLORS.length] + '40',
        },
      };
    });

    return {
      backgroundColor: 'transparent',
      tooltip: {
        backgroundColor: '#ffffff',
        borderColor: '#e5e5e5',
        borderWidth: 1,
        borderRadius: 10,
        padding: [10, 14],
        textStyle: { color: '#1e293b', fontSize: 12 },
        formatter: (params: any) => {
          if (params.dataType === 'edge') {
            return `<div style="font-weight:600;color:#64748b;font-size:11px">供应关系</div>
              <div style="margin-top:4px"><span style="color:#1A56DB;font-weight:600">${params.data.source}</span> → <span style="color:#059669;font-weight:600">${params.data.target}</span></div>`;
          }
          const cat = categories[params.data.category]?.name ?? '';
          return `<div style="font-weight:600;font-size:13px;color:#0A0A0A">${params.name}</div>
            <div style="margin-top:4px;font-size:11px;color:#737373">分类: ${cat}</div>`;
        },
      },
      legend: compact
        ? undefined
        : {
            data: categories.map((c) => c.name),
            type: 'scroll',
            bottom: 4,
            left: 'center',
            textStyle: { fontSize: 11, color: '#64748b' },
            itemWidth: 10,
            itemHeight: 10,
            itemGap: 16,
            icon: 'circle',
            pageTextStyle: { color: '#64748b' },
          },
      series: [
        {
          type: 'graph',
          layout: 'force',
          roam: true,
          draggable: true,
          data: graphData,
          links: links.map((l) => ({
            source: l.source,
            target: l.target,
          })),
          categories,
          force: {
            repulsion: compact ? 160 : 240,
            edgeLength: compact ? 48 : 72,
            gravity: 0.08,
            layoutAnimation: true,
          },
          lineStyle: {
            color: '#e2e8f0',
            width: 0.6,
            curveness: 0.15,
            opacity: 0.6,
          },
          emphasis: {
            focus: 'adjacency',
            lineStyle: { width: 2.5, color: '#1A56DB', opacity: 1 },
            itemStyle: { shadowBlur: 24, shadowColor: '#1A56DB60' },
            label: { fontSize: 14, fontWeight: 700 },
          },
          label: {
            color: '#1e293b',
            fontSize: 11,
            fontWeight: 500,
            backgroundColor: 'rgba(255,255,255,0.85)',
            padding: [2, 8],
            borderRadius: 6,
          },
          scaleLimit: { min: 0.2, max: 4 },
        },
      ],
    };
  }, [nodes, links, compact]);

  /* ── loading ── */
  if (loading) {
    return (
      <div
        className={cn(
          'flex flex-col items-center justify-center rounded-2xl border border-blue-100 bg-gradient-to-b from-white to-blue-50/30',
          className,
        )}
        style={{ height }}
      >
        <div className="relative">
          <div className="absolute inset-0 rounded-full border-4 border-blue-100 animate-ping opacity-20" />
          <Loader2 className="relative h-8 w-8 animate-spin text-blue-500" />
        </div>
        <p className="mt-4 text-sm font-medium text-neutral-600">正在加载产业链数据...</p>
        <p className="mt-1 text-[11px] text-neutral-400">从 Neo4j 图谱中获取节点与关系</p>
      </div>
    );
  }

  /* ── error ── */
  if (error && !nodes.length) {
    return (
      <div
        className={cn(
          'flex flex-col items-center justify-center gap-4 rounded-2xl border border-neutral-100 bg-white p-8',
          className,
        )}
        style={{ height }}
      >
        <div className="rounded-2xl bg-blue-50 p-4">
          <AlertCircle className="h-10 w-10 text-blue-500" />
        </div>
        <div className="text-center">
          <p className="text-sm font-semibold text-neutral-800">图谱数据加载失败</p>
          <p className="mt-1 text-xs text-neutral-500">{error}</p>
          <p className="mt-2 text-[11px] text-neutral-400">请确认 Neo4j 已启动且账号配置正确</p>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          className="flex items-center gap-2 rounded-xl bg-blue-500 px-5 py-2.5 text-xs font-bold text-white hover:bg-blue-600 transition-colors"
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
          'flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-neutral-200 bg-white',
          className,
        )}
        style={{ height }}
      >
        <div className="rounded-full bg-blue-50 p-3">
          <Network className="h-8 w-8 text-blue-400" />
        </div>
        <p className="text-sm font-medium text-neutral-600">暂无图谱数据</p>
        <p className="text-xs text-neutral-400">Neo4j 中尚无 Product 节点或关系</p>
        <button
          type="button"
          onClick={() => void load()}
          className="mt-2 flex items-center gap-1.5 rounded-lg border border-neutral-200 bg-white px-4 py-2 text-xs font-bold text-neutral-600 hover:border-blue-300 hover:text-blue-600 transition-all"
        >
          <RefreshCw className="h-3 w-3" /> 刷新
        </button>
      </div>
    );
  }

  return (
    <div className={cn('relative overflow-hidden rounded-2xl border border-neutral-100 bg-white shadow-sm', className)}>
      {/* top bar with hint */}
      <div className="absolute left-4 top-3 z-10 flex items-center gap-2 rounded-lg bg-white/80 backdrop-blur px-3 py-1.5 border border-neutral-100 shadow-sm">
        <div className="flex items-center gap-3 text-[10px] text-neutral-400">
          <span className="flex items-center gap-1"><MousePointer2 className="h-3 w-3" /> 拖拽节点</span>
          <span className="flex items-center gap-1"><ZoomIn className="h-3 w-3" /> 滚轮缩放</span>
        </div>
      </div>

      {error && (
        <div className="absolute right-3 top-3 z-10 max-w-[260px] rounded-xl border border-amber-200 bg-amber-50/90 backdrop-blur px-3 py-2 text-[11px] text-amber-800 shadow-sm flex items-start gap-2">
          <AlertCircle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {nodes.length > 0 && (
        <p className="absolute right-4 bottom-4 z-10 text-[10px] text-neutral-400">
          {nodes.length} 节点 · {links.length} 关系
        </p>
      )}

      <ReactECharts
        ref={chartRef}
        option={option!}
        style={{ height, width: '100%' }}
        opts={{ renderer: 'canvas' }}
        notMerge
        lazyUpdate
      />
    </div>
  );
}
