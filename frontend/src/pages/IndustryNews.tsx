import { ArrowLeft, Newspaper } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { PublicSiteHeader } from '@/src/components/PublicSiteHeader';

/** 行业资讯占位页，后续承接产业和制造业资讯内容。 */
export default function IndustryNews() {
  const navigate = useNavigate();
  return (
    <div className="public-site min-h-screen bg-public-bg text-public-text">
      <PublicSiteHeader />
      <main className="mx-auto max-w-[1120px] px-4 py-16 md:px-8">
        <section className="rounded-xl border border-public-border bg-public-surface p-8 shadow-public md:p-12">
          <span className="flex h-11 w-11 items-center justify-center rounded-lg bg-public-brand-soft text-public-brand"><Newspaper className="h-5 w-5" /></span>
          <p className="eyebrow mt-6 text-public-brand">Industry news</p>
          <h1 className="mt-3 text-3xl font-black tracking-tight md:text-5xl">行业资讯</h1>
          <p className="mt-4 max-w-2xl text-sm leading-7 text-public-muted">行业资讯栏目正在建设中，后续将提供制造业政策、产业趋势、供应链动态和企业实践内容。</p>
          <button type="button" onClick={() => navigate('/')} className="btn-public-secondary mt-8"><ArrowLeft className="h-4 w-4" />返回首页</button>
        </section>
      </main>
    </div>
  );
}
