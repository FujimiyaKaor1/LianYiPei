import React from 'react';

export default function AdminLegacyFrame({
  title,
  src,
}: {
  title: string;
  src: string;
}) {
  return (
    <div className="flex flex-col h-[calc(100vh-10rem)] min-h-[520px]">
      <p className="text-xs text-neutral-500 mb-2">
        以下为系统内嵌页，若未登录或权限不足可能显示登录页。
      </p>
      <iframe title={title} src={src} className="flex-1 w-full rounded-2xl border border-neutral-200 bg-white" />
    </div>
  );
}
