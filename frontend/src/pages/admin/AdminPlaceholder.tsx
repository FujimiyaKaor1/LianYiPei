import React from 'react';

export default function AdminPlaceholder({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="rounded-2xl border border-dashed border-neutral-300 bg-white p-8 text-center">
      <h2 className="text-lg font-bold text-neutral-800">{title}</h2>
      <p className="text-sm text-neutral-500 mt-3 max-w-lg mx-auto">{description}</p>
    </div>
  );
}
