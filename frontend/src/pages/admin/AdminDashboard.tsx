import React from 'react';
import { Link } from 'react-router-dom';
import { 
  UserCheck, 
  ShieldAlert, 
  KeyRound, 
  Activity, 
  Database,
  Settings2,
  LayoutDashboard
} from 'lucide-react';

export default function AdminDashboard() {
  return (
    <div className="max-w-7xl mx-auto space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      
      {/* 顶层 - 数据看板 (4列 Grid) */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* Card 1: 待审核企业 (使用反色/深灰强调重要性，或用红点) */}
        <div className="bg-white rounded-3xl border border-neutral-200 shadow-sm p-6 relative group overflow-hidden transition-all hover:shadow-md">
          <div className="flex items-center justify-between mb-4 relative z-10">
            <div className="p-3 bg-neutral-100 rounded-2xl group-hover:bg-neutral-200 transition-colors">
              <UserCheck className="w-5 h-5 text-neutral-900" />
            </div>
            <span className="flex h-3 w-3 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-[#CC0000]"></span>
            </span>
          </div>
          <div className="text-neutral-500 text-sm font-medium mb-1 relative z-10">待审核企业</div>
          <div className="text-3xl font-semibold text-neutral-900 relative z-10">12<span className="text-base font-normal text-neutral-400 ml-1">家</span></div>
        </div>

        {/* Card 2: 系统健康度 (纯灰阶) */}
        <div className="bg-white rounded-3xl border border-neutral-200 shadow-sm p-6 group transition-all hover:shadow-md">
          <div className="flex items-center justify-between mb-4">
            <div className="p-3 bg-neutral-100 rounded-2xl group-hover:bg-neutral-200 transition-colors">
              <Activity className="w-5 h-5 text-neutral-900" />
            </div>
            <div className="px-2 py-1 bg-neutral-100 text-neutral-800 border border-neutral-200 rounded-full text-xs font-semibold flex items-center gap-1.5 shadow-sm">
              <div className="w-1.5 h-1.5 rounded-full bg-neutral-900"></div> 运行中
            </div>
          </div>
          <div className="text-neutral-500 text-sm font-medium mb-1">系统健康度</div>
          <div className="text-3xl font-semibold text-neutral-900">98%</div>
        </div>

        {/* Card 3: 拦截恶意报价 */}
        <div className="bg-white rounded-3xl border border-neutral-200 shadow-sm p-6 group transition-all hover:shadow-md">
          <div className="flex items-center justify-between mb-4">
            <div className="p-3 bg-neutral-100 rounded-2xl group-hover:bg-neutral-200 transition-colors">
              <ShieldAlert className="w-5 h-5 text-neutral-900" />
            </div>
          </div>
          <div className="text-neutral-500 text-sm font-medium mb-1">今日拦截恶意报价</div>
          <div className="text-3xl font-semibold text-neutral-900">45<span className="text-base font-normal text-neutral-400 ml-1">次</span></div>
        </div>

        {/* Card 4: API 请求量 */}
        <div className="bg-neutral-50 rounded-3xl border border-neutral-200 shadow-sm p-6 group transition-all hover:shadow-md">
          <div className="flex items-center justify-between mb-4">
            <div className="p-3 bg-white border border-neutral-200 rounded-2xl group-hover:bg-neutral-100 transition-colors">
              <Database className="w-5 h-5 text-neutral-900" />
            </div>
          </div>
          <div className="text-neutral-500 text-sm font-medium mb-1">API接口请求量</div>
          <div className="text-3xl font-semibold text-neutral-900">2.4<span className="text-base font-normal text-neutral-400 ml-1">M</span></div>
        </div>
      </div>

      {/* 中层 - 快捷操作与系统状态 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧大卡片: 快捷操作 Quick Actions (2/3) */}
        <div className="lg:col-span-2 bg-white rounded-3xl border border-neutral-200 shadow-sm p-8">
          <div className="mb-6">
            <h2 className="text-lg font-bold text-neutral-900 tracking-tight">快捷操作 <span className="text-neutral-400 font-normal text-sm ml-2">Quick Actions</span></h2>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {/* Button 1: Primary Action (Solid Black) */}
            <Link to="/admin/dashboard/onboarding" className="flex flex-col items-center justify-center p-6 bg-neutral-900 transition-all rounded-[24px] group hover:scale-[1.02] shadow-md hover:shadow-lg">
              <div className="w-14 h-14 bg-white/10 rounded-2xl flex items-center justify-center mb-4 transition-all duration-300">
                <UserCheck className="w-6 h-6 text-white" />
              </div>
              <span className="text-sm font-semibold text-white">入驻审核</span>
            </Link>
            
            {/* Button 2: Secondary Action (Light Background) */}
            <Link to="/admin/dashboard/rules" className="flex flex-col items-center justify-center p-6 bg-neutral-100 hover:bg-neutral-200 border border-transparent transition-all rounded-[24px] group hover:scale-[1.02]">
              <div className="w-14 h-14 bg-white rounded-2xl shadow-sm border border-neutral-200/50 flex items-center justify-center mb-4 transition-all duration-300">
                <Settings2 className="w-6 h-6 text-neutral-900" />
              </div>
              <span className="text-sm font-semibold text-neutral-800">规则配置</span>
            </Link>

            {/* Button 3: Outlined Action (White with Border) */}
            <Link to="/admin/dashboard/risk" className="flex flex-col items-center justify-center p-6 bg-white border border-neutral-200 hover:border-neutral-400 transition-all rounded-[24px] group hover:shadow-sm">
              <div className="w-14 h-14 bg-neutral-50 rounded-2xl flex items-center justify-center mb-4 transition-all duration-300">
                <ShieldAlert className="w-6 h-6 text-neutral-900" />
              </div>
              <span className="text-sm font-semibold text-neutral-800">预警处置</span>
            </Link>

            {/* Button 4: Outlined Action */}
            <Link to="/admin/dashboard/api-management" className="flex flex-col items-center justify-center p-6 bg-white border border-neutral-200 hover:border-neutral-400 transition-all rounded-[24px] group hover:shadow-sm">
              <div className="w-14 h-14 bg-neutral-50 rounded-2xl flex items-center justify-center mb-4 transition-all duration-300">
                <KeyRound className="w-6 h-6 text-neutral-900" />
              </div>
              <span className="text-sm font-semibold text-neutral-800">接口管理</span>
            </Link>
          </div>
        </div>

        {/* 右侧中卡片: 数据清洗大屏预览 (1/3) - 强反差黑底灰条 */}
        <div className="lg:col-span-1 bg-neutral-900 rounded-3xl border border-neutral-800 shadow-lg p-8 flex flex-col relative overflow-hidden">
          <div className="flex items-center justify-between mb-8 relative z-10">
            <h2 className="text-lg font-bold text-white tracking-tight">数据接入状态</h2>
            <LayoutDashboard className="w-5 h-5 text-neutral-400" />
          </div>
          <div className="flex-1 flex flex-col justify-center space-y-8 relative z-10">
            <div>
              <div className="flex justify-between text-sm mb-3">
                <span className="text-neutral-400 font-medium">当前活跃企业</span>
                <span className="font-bold text-white">140 / 150</span>
              </div>
              <div className="h-2 w-full bg-neutral-700/50 rounded-full overflow-hidden">
                <div className="h-full bg-white rounded-full w-[93%]"></div>
              </div>
            </div>
            
            <div>
              <div className="flex justify-between text-sm mb-3">
                <span className="text-neutral-400 font-medium">已接入数据源</span>
                <span className="font-bold text-white">3 / 5</span>
              </div>
              <div className="h-2 w-full bg-neutral-700/50 rounded-full overflow-hidden">
                <div className="h-full bg-white rounded-full w-[60%]"></div>
              </div>
            </div>

            <div>
              <div className="flex justify-between text-sm mb-3">
                <span className="text-neutral-400 font-medium">存储容量状态</span>
                <span className="font-bold text-white">45%</span>
              </div>
              <div className="h-2 w-full bg-neutral-700/50 rounded-full overflow-hidden">
                <div className="h-full bg-white rounded-full w-[45%]"></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 底层 - 最近动态 */}
      <div className="bg-white rounded-3xl border border-neutral-200 shadow-sm p-8">
        <div className="mb-6">
          <h2 className="text-lg font-bold text-neutral-900 tracking-tight">最近敏感操作日志 <span className="text-neutral-400 font-normal text-sm ml-2">Recent Audit Logs</span></h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr>
                <th className="pb-4 text-xs font-bold text-neutral-500 uppercase tracking-widest pl-2 border-b border-neutral-200">时间</th>
                <th className="pb-4 text-xs font-bold text-neutral-500 uppercase tracking-widest border-b border-neutral-200">操作人</th>
                <th className="pb-4 text-xs font-bold text-neutral-500 uppercase tracking-widest border-b border-neutral-200">动作</th>
                <th className="pb-4 text-xs font-bold text-neutral-500 uppercase tracking-widest text-right pr-2 border-b border-neutral-200">状态</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              <tr className="group hover:bg-neutral-50 transition-colors">
                <td className="py-5 pl-2 text-sm text-neutral-500 whitespace-nowrap">10分钟前</td>
                <td className="py-5 text-sm font-bold text-neutral-900 whitespace-nowrap">系统管理员 Admin</td>
                <td className="py-5 text-sm text-neutral-700">修改了企业信用分计算权重组合规则</td>
                <td className="py-5 pr-2 text-right">
                  <span className="px-2.5 py-1 rounded-md bg-neutral-100 text-neutral-800 border border-neutral-200 text-xs font-bold">成功</span>
                </td>
              </tr>
              <tr className="group hover:bg-neutral-50 transition-colors">
                <td className="py-5 pl-2 text-sm text-neutral-500 whitespace-nowrap">2小时前</td>
                <td className="py-5 text-sm font-bold text-neutral-900 whitespace-nowrap">系统管理员 Admin</td>
                <td className="py-5 text-sm text-neutral-700">封禁了违规企业「智造科技有限公司」</td>
                <td className="py-5 pr-2 text-right">
                  <span className="px-2.5 py-1 rounded-md bg-neutral-100 text-neutral-800 border border-neutral-200 text-xs font-bold">成功</span>
                </td>
              </tr>
              <tr className="group hover:bg-neutral-50 transition-colors">
                <td className="py-5 pl-2 text-sm text-neutral-500 whitespace-nowrap">昨天 15:30</td>
                <td className="py-5 text-sm font-bold text-neutral-900 whitespace-nowrap">系统管理员 Admin</td>
                <td className="py-5 text-sm text-neutral-700">新增了一个工商数据API数据源对接配置</td>
                <td className="py-5 pr-2 text-right">
                  <span className="px-2.5 py-1 rounded-md bg-neutral-100 text-neutral-800 border border-neutral-200 text-xs font-bold">成功</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
