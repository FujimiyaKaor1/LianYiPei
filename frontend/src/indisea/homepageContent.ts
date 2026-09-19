export type CustomerLogo = {
  id: string;
  asset: string;
};

export const customerLogos: CustomerLogo[] = [
  { id: '01', asset: '/indisea/customer-logos/01.svg' },
  { id: '02', asset: '/indisea/customer-logos/02.svg' },
  { id: '04', asset: '/indisea/customer-logos/04.png' },
  { id: '05', asset: '/indisea/customer-logos/05.png' },
  { id: '06', asset: '/indisea/customer-logos/06.svg' },
  { id: '07', asset: '/indisea/customer-logos/07.png' },
  { id: '08', asset: '/indisea/customer-logos/08.png' },
  { id: '09', asset: '/indisea/customer-logos/09.png' },
  { id: '10', asset: '/indisea/customer-logos/10.png' },
  { id: '11', asset: '/indisea/customer-logos/11.png' },
  { id: '12', asset: '/indisea/customer-logos/12.png' },
  { id: '13', asset: '/indisea/customer-logos/13.png' },
  { id: '14', asset: '/indisea/customer-logos/14.png' },
  { id: '15', asset: '/indisea/customer-logos/15.png' },
  { id: '16', asset: '/indisea/customer-logos/16.svg' },
  { id: '17', asset: '/indisea/customer-logos/17.png' },
  { id: '18', asset: '/indisea/customer-logos/18.png' },
  { id: '19', asset: '/indisea/customer-logos/19.png' },
  { id: '21', asset: '/indisea/customer-logos/21.png' },
  { id: '23', asset: '/indisea/customer-logos/23.png' },
  { id: '27', asset: '/indisea/customer-logos/27.png' },
];

export const reasons = [
  {
    title: '找得到，\n却看不懂',
    body: '企业信息分散在名片、表格和熟人网络里。产品是否匹配、产能是否可用、资质是否有效，往往要靠反复确认。',
    color: 'blue',
  },
  {
    title: '需求很急，\n筛选很慢',
    body: '采购方要在距离、产品、产能、信用和历史合作之间取舍。缺少统一依据时，找厂变成一轮轮低效试探。',
    color: 'yellow',
  },
  {
    title: '协同开始后，\n数据没有留下来',
    body: '询价、报价、履约和风险处置各自结束，经验没有回流。企业难以复用判断，园区也难以识别真实缺口。',
    color: 'green',
  },
] as const;

export const benefits = [
  ['01', '先看依据，\n再做判断', '把企业、产品、资质、产能和数据更新时间放在同一条决策链上。'],
  ['02', '从需求出发，\n找到合适的厂', '用产品、距离、产能、信用等信号生成可解释的候选结果。'],
  ['03', '让每次协同，\n留下可用经验', '询价、报价、订单与处置结果回流，为后续合作和产业治理提供依据。'],
] as const;

export const clients = [
  ['采购企业', '寻找可核验的制造能力'],
  ['制造企业', '展示产品、产能与资质'],
  ['园区与政府', '识别缺口、预警与招商线索'],
  ['平台运营方', '审核数据并维护协同秩序'],
] as const;

export const quotes = [
  ['公开页面只呈现脱敏摘要；完整企业能力、联系方式与协同操作需要登录后查看。', '数据边界', '公开找厂'],
  ['从需求到候选结果，平台展示产品、距离、产能、信用等匹配依据，而不是只给出一个黑箱排序。', '匹配依据', '供需协同'],
  ['询价、报价、订单履约和风险处置可以形成可追溯的业务链路，为后续合作和治理提供可用记录。', '结果回流', '产业协同'],
] as const;
