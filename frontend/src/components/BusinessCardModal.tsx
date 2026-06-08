/**
 * 商务名片组件 + 高德地图定位集成
 *
 * 功能：
 * 1. BusinessCardModal - 名片展示弹窗（含高德地图定位）
 * 2. AmapLocation - 高德地图定位展示组件（iframe 嵌入）
 * 3. openAmapNavigation - 打开高德地图导航
 *
 * 高德地图接入方式（选一）：
 *   A. JS API（需要 AMAP_KEY）：https://webapi.amap.com/maps?v=2.0&key=YOUR_KEY
 *   B. URL Scheme（无需 Key）：https://uri.amap.com/navigation?to=lng,lat,name&mode=car
 */

import React from 'react';
import { Building, MapPin, Phone, Award, ShieldCheck, Globe, X, ExternalLink } from 'lucide-react';
import { cn } from '@/src/lib/utils';

// ── 高德地图 URL ──────────────────────────────────────────────────────────

/** 打开高德地图手机 App 导航（无需 Key） */
export function openAmapNavigation(
  longitude: number,
  latitude: number,
  name: string,
  mode: 'car' | 'bus' | 'walk' = 'car',
) {
  const encoded = encodeURIComponent(name);
  const url = `https://uri.amap.com/navigation?to=${longitude},${latitude},${encoded}&mode=${mode}`;
  window.open(url, '_blank', 'noopener,noreferrer');
}

/** 获取高德地图静态图（用于名片展示，无需 Key） */
export function getAmapStaticUrl(
  longitude: number,
  latitude: number,
  width = 280,
  height = 120,
  zoom = 14,
): string {
  return `https://restapi.amap.com/v3/staticmap?location=${longitude},${latitude}&zoom=${zoom}&size=${width}*${height}&markers=mid,,A:${longitude},${latitude}&key=YOUR_AMAP_KEY`;
}

// ── 地图 iframe 组件 ─────────────────────────────────────────────────────

export interface AmapLocationProps {
  longitude: number;
  latitude: number;
  name?: string;
  height?: number;
}

export function AmapLocation({ longitude, latitude, name, height = 160 }: AmapLocationProps) {
  const hasCoords = longitude != null && latitude != null;

  if (!hasCoords) {
    return (
      <div
        className="flex items-center justify-center rounded-xl border border-dashed border-neutral-200 bg-neutral-50"
        style={{ height }}
      >
        <div className="text-center">
          <MapPin className="w-6 h-6 text-neutral-300 mx-auto mb-1" />
          <p className="text-xs text-neutral-400">暂无地理位置信息</p>
        </div>
      </div>
    );
  }

  const pad = 0.012;
  const bbox = `${longitude - pad},${latitude - pad},${longitude + pad},${latitude + pad}`;
  const osmEmbed = `https://www.openstreetmap.org/export/embed.html?bbox=${encodeURIComponent(bbox)}&layer=mapnik&marker=${latitude}%2C${longitude}`;

  return (
    <div className="relative rounded-xl overflow-hidden border border-neutral-100 bg-neutral-50">
      <iframe
        title={name ? `${name} 地图` : '企业位置地图'}
        src={osmEmbed}
        className="w-full border-0 bg-neutral-100"
        style={{ height }}
        loading="lazy"
        referrerPolicy="no-referrer-when-downgrade"
      />
      <div className="p-2 bg-white border-t border-neutral-100 flex items-center justify-between gap-2">
        <span className="text-[10px] text-neutral-400">OpenStreetMap（无需密钥）</span>
        <button
          type="button"
          onClick={() => openAmapNavigation(longitude, latitude, name || '目标位置')}
          className="flex items-center gap-1 text-[10px] font-bold text-blue-600 hover:text-blue-700 transition-colors shrink-0"
        >
          <ExternalLink className="w-3 h-3" />
          高德导航
        </button>
      </div>
    </div>
  );
}

// ── 名片数据接口 ──────────────────────────────────────────────────────────

export interface BusinessCardData {
  id: number;
  name: string;
  address: string;
  longitude: number | null;
  latitude: number | null;
  contact: string;
  phone: string;
  main_business: string;
  credit_score: number;
  is_green_factory: boolean;
  tags: string[];
}

// ── 名片弹窗组件 ──────────────────────────────────────────────────────────

interface BusinessCardModalProps {
  open: boolean;
  myCard?: BusinessCardData;   // 我的名片（当前用户）
  theirCard?: BusinessCardData;  // 对方名片
  onClose: () => void;
}

function SingleCard({
  card,
  label,
  isSelf,
}: {
  card: BusinessCardData;
  label: string;
  isSelf?: boolean;
}) {
  const hasCoords = card.longitude != null && card.latitude != null;

  return (
    <div className="bg-white rounded-2xl border border-neutral-100 shadow-sm overflow-hidden flex flex-col">
      {/* 顶部色条 */}
      <div className="h-1.5 bg-gradient-to-r from-neutral-900 to-neutral-700" />

      <div className="p-5 flex flex-col gap-4 flex-1">
        {/* 企业标识 */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-neutral-900 flex items-center justify-center shrink-0">
              <Building className="w-6 h-6 text-white" />
            </div>
            <div>
              <h3 className="text-base font-bold text-neutral-900 leading-tight">{card.name}</h3>
              {isSelf && (
                <span className="text-[9px] font-bold text-neutral-400 bg-neutral-100 px-1.5 py-0.5 rounded uppercase tracking-widest">
                  我的名片
                </span>
              )}
            </div>
          </div>
          {/* 信用分 */}
          <div className="flex flex-col items-end shrink-0">
            <span className="text-2xl font-black text-neutral-900">{card.credit_score}</span>
            <span className="text-[9px] text-neutral-400">信用分</span>
          </div>
        </div>

        {/* 标签 */}
        <div className="flex flex-wrap gap-1.5">
          {card.is_green_factory && (
            <span className="inline-flex items-center gap-1 text-[9px] font-bold text-blue-700 bg-blue-50 border border-blue-100 px-2 py-1 rounded-full">
              <ShieldCheck className="w-2.5 h-2.5 fill-blue-400" />
              政府绿标
            </span>
          )}
          {card.tags.slice(0, 3).map((tag, i) => (
            <span
              key={i}
              className="text-[9px] font-medium text-neutral-600 bg-neutral-100 px-2 py-1 rounded-full"
            >
              {tag}
            </span>
          ))}
        </div>

        {/* 地图 */}
        <AmapLocation
          longitude={card.longitude!}
          latitude={card.latitude!}
          name={card.name}
          height={120}
        />

        {/* 联系信息 */}
        <div className="space-y-2">
          <div className="flex items-start gap-2">
            <MapPin className="w-3.5 h-3.5 text-neutral-400 mt-0.5 shrink-0" />
            <span className="text-xs text-neutral-600 leading-snug">{card.address}</span>
          </div>
          {card.phone && (
            <div className="flex items-center gap-2">
              <Phone className="w-3.5 h-3.5 text-neutral-400 shrink-0" />
              <a
                href={`tel:${card.phone}`}
                className="text-xs text-primary font-medium hover:underline"
              >
                {card.phone}
              </a>
            </div>
          )}
          {card.contact && (
            <div className="flex items-center gap-2">
              <Award className="w-3.5 h-3.5 text-neutral-400 shrink-0" />
              <span className="text-xs text-neutral-600">{card.contact}</span>
            </div>
          )}
          {card.main_business && (
            <div className="flex items-start gap-2">
              <Globe className="w-3.5 h-3.5 text-neutral-400 mt-0.5 shrink-0" />
              <span className="text-xs text-neutral-500 leading-snug">{card.main_business}</span>
            </div>
          )}
        </div>
      </div>

      {/* 底部标签 */}
      <div className="px-5 pb-3 flex items-center justify-between">
        <span className="text-[9px] text-neutral-300">{label}</span>
        {hasCoords && (
          <button
            type="button"
            onClick={() => openAmapNavigation(card.longitude!, card.latitude!, card.name)}
            className="flex items-center gap-1 text-[9px] font-bold text-blue-600 hover:text-blue-700 transition-colors"
          >
            <MapPin className="w-2.5 h-2.5" />
            高德导航
          </button>
        )}
      </div>
    </div>
  );
}

export function BusinessCardModal({
  open,
  myCard,
  theirCard,
  onClose,
}: BusinessCardModalProps) {
  if (!open) return null;

  const hasBoth = Boolean(myCard) && Boolean(theirCard);

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="w-full max-w-2xl bg-neutral-50 rounded-3xl shadow-2xl overflow-hidden max-h-[90vh] flex flex-col">
        {/* 标题栏 */}
        <div className="px-6 py-4 bg-white border-b border-neutral-100 flex items-center justify-between shrink-0">
          <div>
            <h2 className="text-base font-bold text-neutral-900">
              {hasBoth ? '名片交换成功' : '企业名片'}
            </h2>
            <p className="text-xs text-neutral-400 mt-0.5">
              {hasBoth
                ? '双方已达成合作，名片信息已解锁'
                : '查看企业联系信息与地理位置'}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-xl text-neutral-400 hover:bg-neutral-100 hover:text-neutral-700 transition-colors"
            aria-label="关闭"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* 名片内容 */}
        <div className="flex-1 overflow-y-auto p-4">
          {hasBoth ? (
            <div className="grid grid-cols-2 gap-4">
              {myCard && <SingleCard card={myCard} label="我方企业" isSelf />}
              {theirCard && <SingleCard card={theirCard} label="合作企业" />}
            </div>
          ) : myCard ? (
            <SingleCard card={myCard} label="企业名片" />
          ) : theirCard ? (
            <SingleCard card={theirCard} label="企业名片" />
          ) : null}
        </div>

        {/* 底部操作 */}
        {hasBoth && (
          <div className="px-6 py-4 bg-white border-t border-neutral-100 flex justify-end shrink-0">
            <button
              type="button"
              onClick={onClose}
              className="px-6 py-2.5 bg-neutral-900 text-white rounded-xl text-sm font-bold hover:bg-neutral-800 transition-colors"
            >
              完成
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
