import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronLeft, Database, Maximize2, Network, RefreshCw } from 'lucide-react';
import { GovSupplyChainGraph } from '@/src/components/GovSupplyChainGraph';

export default function GovSupplyChain() {
  const [chartHeight, setChartHeight] = useState(560);
  const [compactGraph, setCompactGraph] = useState(false);

  useEffect(() => {
    const update = () => {
      const isNarrow = window.innerWidth < 768;
      setCompactGraph(isNarrow);
      setChartHeight(
        isNarrow
          ? Math.min(620, Math.max(460, window.innerHeight - 230))
          : Math.min(720, Math.max(400, window.innerHeight - 220)),
      );
    };
    update();
    window.addEventListener('resize', update);
    return () => window.removeEventListener('resize', update);
  }, []);

  return (
    <div className="mx-auto max-w-[1440px] space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <Link
          to="/gov"
          className="flex items-center gap-1 text-xs font-bold text-ink-muted transition-colors hover:text-brand"
        >
          <ChevronLeft className="h-4 w-4" /> 返回监管首页
        </Link>
      </div>

      <section className="panel overflow-hidden">
        <div className="grid grid-cols-1 lg:grid-cols-[1.25fr_0.75fr]">
          <div className="relative overflow-hidden bg-sidebar-bg p-7 text-sidebar-text-active">
            <div className="absolute inset-0 bg-grid-fade opacity-20" />
            <div className="relative max-w-3xl">
              <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-md border border-white/10 bg-brand text-white shadow-elevation-2">
                <Network className="h-5 w-5" />
              </div>
              <p className="mb-2 text-xs font-bold uppercase text-sidebar-text">Knowledge Graph</p>
              <h1 className="text-2xl font-black text-sidebar-text-active">全平台产业链图谱</h1>
              <p className="mt-3 text-sm leading-6 text-sidebar-text">
                以 Neo4j 关系网络展示企业、产品与供应链连接。节点大小随连接度增强，颜色代表分类，可拖拽、缩放并聚焦上下游关系。
              </p>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3 bg-surface p-5">
            {[
              { icon: Database, label: '数据源', value: 'Neo4j' },
              { icon: RefreshCw, label: '布局', value: 'Force' },
              { icon: Maximize2, label: '交互', value: '缩放拖拽' },
            ].map((item) => (
              <div key={item.label} className="rounded-md border border-border bg-surface-subtle p-4">
                <item.icon className="mb-3 h-4 w-4 text-brand" />
                <div className="text-[10px] font-bold uppercase text-ink-muted">{item.label}</div>
                <div className="metric-number mt-1 text-sm font-black text-ink">{item.value}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <GovSupplyChainGraph height={chartHeight} compact={compactGraph} />
    </div>
  );
}
