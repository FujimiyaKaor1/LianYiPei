import { useEffect, useRef, useState, type CSSProperties } from 'react';
import { benefits, clients, customerLogos, quotes, reasons, type CustomerLogo } from './homepageContent';
import ScrollSpine from './ScrollSpine';
import { SectionLabel, TalkButton } from './SiteChrome';

function Hero() {
  const [activeWord, setActiveWord] = useState(0);
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const timer = window.setInterval(() => setActiveWord((value) => (value + 1) % 3), 2200);
    return () => window.clearInterval(timer);
  }, []);

  const wordClass = (index: number) => index === activeWord ? 'is-active' : '';
  return (
    <section className="indisea-hero" data-spine-section="01" aria-labelledby="hero-title">
      <div data-motion-reveal><SectionLabel>01 / 英雄</SectionLabel></div>
      <h1 id="hero-title" aria-label="让需求找到、匹配、评估优质的制造能力">
        <span>让需求</span>
        <span className="indisea-hero__verbs"><mark className={wordClass(0)}>找到</mark><i>·</i><mark className={wordClass(1)}>匹配</mark><i>·</i><mark className={wordClass(2)}>评估</mark></span>
        <span>优质的制造能力</span>
      </h1>
      <div data-motion-reveal><TalkButton className="indisea-hero__cta" href="/search" label="开始找厂" /></div>
      <a className="indisea-scroll" href="#connector-wall"><span aria-hidden="true">↓</span> 向下滚动</a>
    </section>
  );
}

function CustomerLogoCard({ logo }: { logo: CustomerLogo }) {
  return (
    <article className="indisea-logo-card" data-motion-reveal>
      <img className="indisea-logo-card__image" src={`${import.meta.env.BASE_URL}${logo.asset.slice(1)}`} alt={`企业标识 ${logo.id}`} />
    </article>
  );
}

function CustomerLogoRow({ reverse = false, decorative = false }: { reverse?: boolean; decorative?: boolean }) {
  const items = reverse ? [...customerLogos].reverse() : customerLogos;
  return (
    <div className={`indisea-logo-row ${reverse ? 'is-reverse' : ''}`} aria-hidden={decorative || undefined}>
      <div className="indisea-logo-track" data-logo-duration={reverse ? '69' : '62'} aria-label={reverse ? '企业标识，反向滚动' : '企业标识'}>
        {items.map((logo) => <div key={logo.id}><CustomerLogoCard logo={logo} /></div>)}
        <div className="indisea-logo-track__duplicate" aria-hidden="true">
          {items.map((logo) => <div key={`${logo.id}-duplicate`}><CustomerLogoCard logo={logo} /></div>)}
        </div>
      </div>
    </div>
  );
}

function ConnectorWall() {
  return (
    <section id="connector-wall" className="indisea-connector-wall" data-spine-section="02">
      <SectionLabel>02 / 十二项协同能力</SectionLabel>
      <CustomerLogoRow />
      <CustomerLogoRow reverse decorative />
    </section>
  );
}

function WhoWeAre() {
  return (
    <section className="indisea-who" data-spine-section="03">
      <div className="indisea-who__content" data-motion-reveal>
        <SectionLabel>03 / 我们是谁</SectionLabel>
        <p className="indisea-lede">链易配是面向地方产业链的协同操作台，让采购方找到可核验的制造能力，让制造企业更清楚地被看见。</p>
        <p className="indisea-body-copy">平台把<mark>企业画像、产品能力、产能、信用和履约信号</mark>连接起来，服务企业之间的供需协同，也为园区和政府提供补链、强链的可用依据。</p>
      </div>
      <div className="indisea-stats" data-spine-waypoint="stats">
        {[
          ['3054', '4', '', '演示企业档案'],
          ['7602', '4', '', '演示产品节点'],
          ['4', '2', '', '开放采购需求'],
          ['3', '2', '', '已完成订单'],
        ].map(([target, pad, suffix, label]) => <article key={label} data-motion-reveal><strong data-count-target={target} data-count-pad={pad} data-count-suffix={suffix}>{`${target}${suffix}`}</strong><span>{label}</span></article>)}
      </div>
    </section>
  );
}

function ProblemStory() {
  const section = useRef<HTMLElement>(null);
  const [stage, setStage] = useState(0);

  useEffect(() => {
    let frame = 0;
    const update = () => {
      const node = section.current;
      if (!node) return;
      const rect = node.getBoundingClientRect();
      const available = Math.max(1, rect.height - window.innerHeight);
      const progress = Math.min(1, Math.max(0, -rect.top / available));
      const nextStage = progress >= .66 ? 4 : progress >= .40 ? 3 : progress >= .23 ? 2 : progress >= .06 ? 1 : 0;
      setStage((current) => current === nextStage ? current : nextStage);
    };
    const onScroll = () => {
      window.cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(update);
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll);
    update();
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', onScroll);
    };
  }, []);

  return (
    <section ref={section} className="indisea-problem-story" data-spine-section="04">
      <div className="indisea-problem-story__sticky">
        <SectionLabel>04 / 当前难题</SectionLabel>
        <h2>
          <span><i className={stage >= 1 ? 'is-visible' : ''}>找工厂</i></span>
          <span><i className={stage >= 2 ? 'is-visible' : ''}>不该只靠熟人</i></span>
          <span><i className={stage >= 3 ? 'is-visible' : ''}>也不该反复试探。</i></span>
        </h2>
        <div className={`indisea-problem-story__fine ${stage >= 4 ? 'is-visible' : ''}`}><span aria-hidden="true" /><p>一次采购不只是在目录里挑选。产品是否适配、产能能否承接、企业是否可信，都需要有来源、有时间、有边界的数据支撑。</p><p>链易配把这些判断依据放到同一处，让协同从“问一圈”变成“看明白再行动”。</p></div>
      </div>
    </section>
  );
}

const diagramNodes = [
  ['企业档案', 'blue'],
  ['供需发布', 'green'],
  ['询价报价', 'yellow'],
  ['订单履约', 'red'],
] as const;

function ConnectionDiagram() {
  return (
    <div className="indisea-diagram" data-spine-waypoint="diagram" data-draw-group data-motion-reveal aria-label="采购需求连接企业档案、供需发布、询价报价和订单履约">
      <svg viewBox="0 0 760 620" preserveAspectRatio="none" aria-hidden="true">
        <path data-draw-path d="M110 310H300" />
        <path data-draw-path d="M380 310H490C545 310 565 270 565 225V80H665" />
        <path data-draw-path d="M380 310H665" />
        <path data-draw-path d="M380 310H490C545 310 565 350 565 395V540H665" />
        <path data-draw-path d="M565 310V225H665" />
      </svg>
      <div className="indisea-diagram__source"><svg viewBox="0 0 32 32" aria-hidden="true"><rect x="4" y="5" width="24" height="17" rx="2" /><path d="M11 27h10M16 22v5" /></svg><span>采购需求</span></div>
      <div className="indisea-diagram__center"><b>链</b></div>
      <div className="indisea-diagram__targets">{diagramNodes.map(([name, color], index) => <div className={`indisea-diagram__node node-${index + 1} is-${color}`} key={name}><b>{index + 1}</b><span>{name}</span></div>)}</div>
    </div>
  );
}

function WhatChanges() {
  return (
    <section className="indisea-changes" data-spine-section="05">
      <SectionLabel>05 / 链易配如何连接</SectionLabel>
      <div className="indisea-changes__grid">
        <div className="indisea-changes__copy" data-motion-reveal><h2>把一次供需协同，串成一条看得见的业务链。</h2><p>采购需求进入平台后，系统从企业、产品、产能、距离、信用等可用信号中筛选候选对象，并将匹配依据清楚呈现。</p><p>后续的询价、报价、订单履约和风险处置继续沉淀为记录，让企业协同与产业治理使用同一份可追溯依据。</p><div className="indisea-change-tags"><span>可核验数据</span><span>可解释匹配</span><span>协同结果回流</span></div></div>
        <ConnectionDiagram />
      </div>
    </section>
  );
}

function Reasons() {
  return (
    <section className="indisea-reasons" data-spine-section="07" data-spine-waypoint="reasons" aria-label="链易配解决的协同问题">
      {reasons.map((reason, index) => (
        <article className={`indisea-reason is-${reason.color}`} style={{ '--stack-offset': `${index * 28}px`, '--mobile-stack-offset': `${index * 18}px` } as CSSProperties} key={reason.title}>
          <div className="indisea-reason__meta"><SectionLabel>07 / 为什么需要链易配</SectionLabel><span className="indisea-reason__number">场景 {index + 1}</span></div>
          <div className="indisea-reason__copy" data-motion-reveal><h2>{reason.title}</h2><p>{reason.body}</p></div>
          <strong className="indisea-reason__ordinal" aria-hidden="true">{index + 1}</strong>
        </article>
      ))}
    </section>
  );
}

function Benefits() {
  return (
    <section className="indisea-benefits" data-spine-section="08">
      <SectionLabel>08 / 你能得到什么</SectionLabel>
      <div>{benefits.map(([number, title, body]) => <article key={number} data-motion-reveal><span className="indisea-benefit__number">{number}</span><h3>{title}</h3><p>{body}</p></article>)}</div>
    </section>
  );
}

function Clients() {
  return (
    <section className="indisea-clients" data-spine-section="09">
      <SectionLabel>09 / 为谁而建</SectionLabel>
      <p data-motion-reveal>链易配服务于需要<mark>找得到、看得懂、敢合作、能监管</mark>的产业协同参与者，让不同角色在同一套事实依据上完成下一步行动。</p>
      <div data-spine-waypoint="clients">{clients.map(([name, sector]) => <article key={name} data-motion-reveal><strong>{name}</strong><span>{sector}</span></article>)}</div>
    </section>
  );
}

function Proof() {
  return (
    <section className="indisea-proof" data-spine-section="10">
      <SectionLabel>10 / 协同依据</SectionLabel>
      <h2 data-motion-reveal>不是一句推荐，<br />而是过程中的依据</h2>
      <div>{quotes.map(([quote, role, company]) => <blockquote key={company} data-motion-reveal><p>“{quote}”</p><footer><div><strong>{role}</strong><cite>{company}</cite></div></footer></blockquote>)}</div>
    </section>
  );
}

function FinalCta() {
  return (
    <section className="indisea-final-cta" data-spine-section="11">
      <SectionLabel>11 / 开始协同</SectionLabel>
      <h2><span data-cta-line>从一条真实需求</span><span data-cta-line>开始，连接</span><span data-cta-line>可靠的制造能力。</span></h2>
      <div data-motion-reveal><TalkButton href="/search" label="开始找厂" /><a href="/aia">AI 找工厂</a><a href="/#services">查看服务</a></div>
    </section>
  );
}

export default function HomePage() {
  return <main id="top" className="indisea-page"><ScrollSpine /><Hero /><ConnectorWall /><WhoWeAre /><ProblemStory /><WhatChanges /><Reasons /><Benefits /><Clients /><Proof /><FinalCta /></main>;
}
