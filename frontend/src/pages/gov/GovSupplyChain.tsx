import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronLeft, Network } from 'lucide-react';
import { GovSupplyChainGraph } from '@/src/components/GovSupplyChainGraph';

export default function GovSupplyChain() {
  const [chartHeight, setChartHeight] = useState(560);

  useEffect(() => {
    const update = () => setChartHeight(Math.min(720, Math.max(400, window.innerHeight - 220)));
    update();
    window.addEventListener('resize', update);
    return () => window.removeEventListener('resize', update);
  }, []);

  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Link
          to="/gov"
          className="flex items-center gap-1 text-xs font-bold text-neutral-500 hover:text-black"
        >
          <ChevronLeft className="h-4 w-4" /> 返回监管首页
        </Link>
        <div className="flex items-center gap-2">
          <Network className="h-5 w-5 text-neutral-700" />
          <div>
            <h1 className="text-lg font-black tracking-tight">全平台产业链图谱</h1>
            <p className="text-[11px] text-neutral-500">
              数据来自 Neo4j（Product 节点与 SUPPLIES_TO 关系）；下图按规模采样以保障流畅交互，与平台企业填报的供应关系一致。
            </p>
          </div>
        </div>
      </div>
      <GovSupplyChainGraph height={chartHeight} compact={false} />
    </div>
  );
}
