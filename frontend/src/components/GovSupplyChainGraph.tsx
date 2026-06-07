/**
 * 政府端：Neo4j 全平台产业链关系图（ECharts force graph）
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import { Loader2, AlertCircle, RefreshCw } from 'lucide-react';
import { cn } from '@/src/lib/utils';
import { api } from '@/src/services/api';

type GraphNode = { name: string; category?: string };
type GraphLink = { source: string; target: string };

interface GovSupplyChainGraphProps {
  height: number;
  /** 更少节点、更短超时，适合监管首页嵌入 */
  compact?: boolean;
  className?: string;
}

export function GovSupplyChainGraph({ height, compact, className }: GovSupplyChainGraphProps) {
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [links, setLinks] = useState<GraphLink[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
    const categories = [...catSet].map((name) => ({ name }));
    const nameToCatIndex = new Map(categories.map((c, i) => [c.name, i]));
    const showLabels = !compact || nodes.length <= 72;
    const graphData = nodes.map((n) => {
      const cn = (n.category || '未分类').trim() || '未分类';
      return {
        name: n.name,
        category: nameToCatIndex.get(cn) ?? 0,
        symbolSize: compact ? 16 : 22,
        label: { show: showLabels, fontSize: 10 },
      };
    });
    return {
      tooltip: {},
      legend: compact
        ? undefined
        : {
            data: categories.map((c) => c.name),
            type: 'scroll',
            bottom: 0,
            textStyle: { fontSize: 10 },
          },
      series: [
        {
          type: 'graph',
          layout: 'force',
          roam: true,
          draggable: true,
          data: graphData,
          links: links.map((l) => ({ source: l.source, target: l.target })),
          categories,
          force: {
            repulsion: compact ? 100 : 180,
            edgeLength: compact ? 36 : 56,
            gravity: 0.1,
          },
          lineStyle: { color: '#cbd5e1', width: 0.8, curveness: 0.12 },
          emphasis: { focus: 'adjacency', lineStyle: { width: 2 } },
          label: { color: '#475569' },
        },
      ],
    };
  }, [nodes, links, compact]);

  if (loading) {
    return (
      <div
        className={cn(
          'flex flex-col items-center justify-center rounded-2xl border border-neutral-100 bg-white',
          className,
        )}
        style={{ height }}
      >
        <Loader2 className="h-6 w-6 animate-spin text-neutral-300" />
        <p className="mt-2 text-xs text-neutral-400">正在加载 Neo4j 产业链数据…</p>
      </div>
    );
  }

  if (error && !nodes.length) {
    return (
      <div
        className={cn(
          'flex flex-col items-center justify-center gap-3 rounded-2xl border border-neutral-100 bg-neutral-50 p-6',
          className,
        )}
        style={{ height }}
      >
        <AlertCircle className="h-8 w-8 text-amber-400" />
        <p className="text-center text-xs text-neutral-600">{error}</p>
        <p className="text-center text-[10px] text-neutral-400">请确认 Neo4j 已启动且账号配置正确</p>
        <button
          type="button"
          onClick={() => void load()}
          className="flex items-center gap-1.5 rounded-lg border border-neutral-200 bg-white px-3 py-1.5 text-xs font-bold text-neutral-700 hover:border-black"
        >
          <RefreshCw className="h-3.5 w-3.5" /> 重试
        </button>
      </div>
    );
  }

  if (!nodes.length) {
    return (
      <div
        className={cn(
          'flex flex-col items-center justify-center rounded-2xl border border-dashed border-neutral-200 bg-white',
          className,
        )}
        style={{ height }}
      >
        <p className="text-xs text-neutral-500">暂无图谱数据（Neo4j 中尚无 Product 节点或关系）</p>
        <button
          type="button"
          onClick={() => void load()}
          className="mt-3 flex items-center gap-1 text-[10px] font-bold text-neutral-400 hover:text-black"
        >
          <RefreshCw className="h-3 w-3" /> 刷新
        </button>
      </div>
    );
  }

  return (
    <div className={cn('relative overflow-hidden rounded-2xl border border-neutral-100 bg-white', className)}>
      {error && (
        <div className="absolute right-2 top-2 z-10 max-w-[220px] rounded-lg border border-amber-200 bg-amber-50 px-2 py-1 text-[10px] text-amber-900">
          {error}
        </div>
      )}
      <ReactECharts
        option={option!}
        style={{ height, width: '100%' }}
        opts={{ renderer: 'canvas' }}
        notMerge
        lazyUpdate
      />
    </div>
  );
}
