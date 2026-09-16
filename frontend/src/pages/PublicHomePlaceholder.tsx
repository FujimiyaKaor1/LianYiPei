import { ArrowRight, Sparkles } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { PublicSiteHeader } from '@/src/components/PublicSiteHeader';

/** 首页占位：待品牌首页内容确认后替换，找厂能力统一从 AI 找工厂进入。 */
export default function PublicHomePlaceholder() {
  const navigate = useNavigate();
  return (
    <div className="public-site min-h-screen bg-public-bg text-public-text">
      <PublicSiteHeader />
      <main className="mx-auto flex min-h-[calc(100vh-70px)] max-w-[1120px] items-center justify-center px-4 py-16 md:px-8">
        <section className="w-full max-w-2xl rounded-xl border border-public-border bg-public-surface p-8 text-center shadow-public md:p-14">
          <p className="eyebrow text-public-brand">链易配 · 制造业协同平台</p>
          <h1 className="mt-4 text-3xl font-black tracking-tight md:text-5xl">首页正在准备中</h1>
          <p className="mx-auto mt-4 max-w-lg text-sm leading-7 text-public-muted">
            首页新版内容即将上线。查工厂、找老板、找渠道等现有能力，请从 AI 找工厂进入。
          </p>
          <button type="button" onClick={() => navigate('/aia')} className="btn-public-primary mt-8">
            <Sparkles className="h-4 w-4" />进入 AI 找工厂<ArrowRight className="h-4 w-4" />
          </button>
        </section>
      </main>
    </div>
  );
}
