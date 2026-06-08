import React, { useEffect, useState } from 'react';
import { 
  Wallet, 
  ShieldCheck, 
  Award, 
  TrendingUp, 
  Users, 
  Plus, 
  ChevronRight, 
  FileText, 
  Lock, 
  Database,
  ArrowUpRight,
  MapPin,
  Building2,
  Loader2,
  AlertTriangle
} from 'lucide-react';
import { motion } from 'motion/react';
import { cn } from '@/src/lib/utils';
import { api, type EnterpriseAssetData, NETWORK_ERROR_MESSAGE } from '@/src/services/api';

export default function Assets() {
  const [data, setData] = useState<EnterpriseAssetData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorText, setErrorText] = useState('');

  const loadData = async () => {
    setIsLoading(true);
    setErrorText('');
    try {
      const res = await api.getAssets();
      setData(res.assets || null);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : NETWORK_ERROR_MESSAGE);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, []);

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-32 text-neutral-300">
        <Loader2 className="w-8 h-8 animate-spin mb-4 text-neutral-400" />
      </div>
    );
  }

  if (errorText || !data) {
    return (
      <div className="bg-red-50 border border-red-100 rounded-xl px-4 py-8 text-xs text-red-600 font-medium flex flex-col items-center justify-center gap-4">
        <AlertTriangle className="w-8 h-8 opacity-80" />
        {errorText || "无法加载企业画像数据"}
        <button onClick={() => void loadData()} className="mt-2 text-white bg-red-500 hover:bg-red-600 px-4 py-2 rounded-lg font-bold">重新加载</button>
      </div>
    );
  }

  return (
    <div className="space-y-12">
      {/* Identity Banner */}
      <section className="bg-black text-white rounded-[3rem] p-12 relative overflow-hidden shadow-2xl">
        <div className="absolute top-0 right-0 w-[600px] h-[600px] bg-gradient-to-br from-white/10 to-transparent blur-3xl rounded-full -mr-64 -mt-64"></div>
        
        <div className="relative z-10 flex flex-col lg:flex-row justify-between items-start lg:items-center gap-12">
          <div className="flex items-center gap-10">
            <div className="w-32 h-32 bg-white rounded-[2.5rem] flex items-center justify-center text-black font-black text-4xl shadow-xl shrink-0 uppercase">
              {data.name.slice(0, 1)}
            </div>
            <div>
              <div className="flex items-center gap-4 mb-3">
                <h1 className="text-4xl font-extrabold tracking-tight">{data.name}</h1>
                {data.is_certified && (
                  <span className="px-3 py-1 bg-blue-500/20 text-blue-400 text-[10px] font-black rounded uppercase tracking-widest border border-green-500/30">已认证</span>
                )}
              </div>
              <div className="flex flex-wrap gap-6 text-sm text-neutral-400 font-medium mt-4">
                <span className="flex items-center gap-2"><MapPin className="w-4 h-4" /> {data.location}</span>
                <span className="flex items-center gap-2"><Building2 className="w-4 h-4" /> 制造业 · {data.industry_tag}</span>
                {data.tags.slice(0, 1).map((tag, i) => (
                  <span key={i} className="flex items-center gap-2"><Award className="w-4 h-4" /> {tag}</span>
                ))}
              </div>
            </div>
          </div>
          
          <div className="flex gap-8 shrink-0">
            <div className="text-center">
              <div className="text-5xl font-black tracking-tighter">{data.credit_score}</div>
              <div className="text-[10px] text-neutral-400 font-bold uppercase tracking-widest mt-2">履约信用分</div>
            </div>
            <div className="w-px h-16 bg-white/10"></div>
            <div className="text-center">
              <div className="text-5xl font-black tracking-tighter">{data.patent_count}</div>
              <div className="text-[10px] text-neutral-400 font-bold uppercase tracking-widest mt-2">核心专利</div>
            </div>
          </div>
        </div>
      </section>

      {/* Grid Content */}
      <section className="grid grid-cols-12 gap-10">
        {/* Left: Certifications & Data */}
        <div className="col-span-12 lg:col-span-8 space-y-10">
          {/* Certifications */}
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <h3 className="text-xl font-bold">企业资质与证书</h3>
              <button className="text-xs font-bold text-neutral-400 hover:text-black flex items-center gap-1 transition-colors">
                上传新证书 <Plus className="w-4 h-4" />
              </button>
            </div>
            <div className="grid grid-cols-2 gap-6">
              {data.qualifications.map((cert, i) => (
                <div key={i} className="p-6 bg-white rounded-3xl border border-neutral-100 shadow-sm flex items-center justify-between group cursor-pointer hover:shadow-md transition-all">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 bg-neutral-50 rounded-2xl flex items-center justify-center text-neutral-400 group-hover:text-black transition-colors">
                      <FileText className="w-6 h-6" />
                    </div>
                    <div>
                      <h4 className="text-sm font-bold">{cert.title}</h4>
                      <p className="text-[10px] text-neutral-400 mt-1">{cert.date}</p>
                    </div>
                  </div>
                  {cert.status === '有效' && <ShieldCheck className="w-5 h-5 text-blue-500" />}
                </div>
              ))}
              {data.qualifications.length === 0 && (
                <div className="col-span-2 py-8 text-center text-sm text-neutral-400 border-2 border-dashed border-neutral-100 rounded-3xl">
                  暂无资质信息
                </div>
              )}
            </div>
          </div>

          {/* Data Auth */}
          <div className="space-y-6">
            <h3 className="text-xl font-bold">数据授权接口</h3>
            <div className="bg-white rounded-[2.5rem] border border-neutral-100 shadow-sm overflow-hidden">
              <div className="p-8 border-b border-neutral-50 flex justify-between items-center">
                <div className="flex items-center gap-3">
                  <Database className="w-5 h-5 text-black" />
                  <span className="text-sm font-bold">外部系统同步状态</span>
                </div>
                <span className="text-[10px] text-neutral-400 font-bold">最后同步：10分钟前</span>
              </div>
              <div className="divide-y divide-neutral-50">
                {data.data_auth.map((sys, i) => (
                  <div key={i} className="p-8 flex items-center justify-between hover:bg-neutral-50/50 transition-colors">
                    <div className="flex items-center gap-6">
                      <div className="w-10 h-10 bg-neutral-100 rounded-xl flex items-center justify-center">
                        <Building2 className="w-5 h-5 text-neutral-400" />
                      </div>
                      <div>
                        <h4 className="text-sm font-bold">{sys.name}</h4>
                        <p className="text-[10px] text-neutral-400 mt-1">同步内容：{sys.data}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-6">
                      <span className={cn(
                        "px-3 py-1 rounded-full text-[10px] font-bold",
                        sys.status === '已连接' ? "bg-blue-50 text-blue-600" : "bg-neutral-100 text-neutral-400"
                      )}>{sys.status}</span>
                      <button className="p-2 hover:bg-white rounded-lg transition-all">
                        {sys.status === '已连接' ? <Lock className="w-4 h-4 text-neutral-400" /> : <Plus className="w-4 h-4 text-neutral-400" />}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Right: Team & Credit */}
        <div className="col-span-12 lg:col-span-4 space-y-10">
          {/* Credit Score Detail */}
          <div className="bg-surface-container-highest rounded-[2.5rem] p-10 space-y-8 shadow-sm">
            <h4 className="text-lg font-bold">信用分构成</h4>
            <div className="space-y-6">
              {data.credit_breakdown.map((item, i) => (
                <div key={i} className="space-y-2">
                  <div className="flex justify-between text-[10px] font-bold uppercase tracking-widest">
                    <span>{item.label}</span>
                    <span>{item.score}</span>
                  </div>
                  <div className="w-full h-1.5 bg-neutral-100 rounded-full overflow-hidden">
                    <div 
                      className={cn("h-full transition-all duration-1000", item.score > 80 ? 'bg-black' : 'bg-neutral-400')} 
                      style={{ width: `${Math.max(0, Math.min(100, item.score))}%` }}>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <p className="text-[11px] text-neutral-500 leading-relaxed italic">
              * 信用分由 AI 引擎根据链上存证、税务公开数据及行业评价实时计算得出。
            </p>
          </div>

          {/* Team Management */}
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-bold">团队成员</h3>
              <button className="text-xs font-bold text-black border border-neutral-200 px-3 py-1.5 rounded-lg hover:bg-neutral-50 transition-colors">管理</button>
            </div>
            <div className="space-y-3">
              {data.team_members.map((member, i) => (
                <div key={i} className="p-4 bg-white rounded-2xl border border-neutral-100 shadow-sm flex items-center justify-between group cursor-pointer hover:bg-neutral-50 transition-colors">
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 bg-neutral-900 text-white rounded-full flex items-center justify-center font-bold text-xs shrink-0">{member.avatar}</div>
                    <div>
                      <h4 className="text-sm font-bold truncate max-w-[120px]">{member.name}</h4>
                      <p className="text-[10px] text-neutral-400 truncate max-w-[120px]">{member.role}</p>
                    </div>
                  </div>
                  <ChevronRight className="w-4 h-4 text-neutral-300 group-hover:text-black shrink-0" />
                </div>
              ))}
              <button className="w-full py-4 border-2 border-dashed border-neutral-200 rounded-2xl text-xs font-bold text-neutral-500 hover:border-black hover:text-black transition-all flex items-center justify-center gap-2">
                <Plus className="w-4 h-4" /> 邀请新成员
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
