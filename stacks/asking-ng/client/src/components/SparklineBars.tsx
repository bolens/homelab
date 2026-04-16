import React from 'react';

type SparklineBarsProps = {
  values: number[];
  bucketLabel: (index: number) => string;
  maxHeightPx?: number;
  barWidthPx?: number;
};

export default function SparklineBars({
  values,
  bucketLabel,
  maxHeightPx = 22,
  barWidthPx = 4,
}: SparklineBarsProps) {
  const safeValues = values.map((v) => (Number.isFinite(v) && v > 0 ? v : 0));
  const max = safeValues.reduce((m, v) => (v > m ? v : m), 0);
  const denom = max > 0 ? max : 1;
  return (
    <>
      {safeValues.map((v, i) => (
        <span
          key={i}
          title={`${bucketLabel(i)} - ${v}`}
          style={{
            display: 'inline-block',
            width: `${barWidthPx}px`,
            height: `${Math.max(2, Math.round((v / denom) * maxHeightPx))}px`,
            marginRight: i === safeValues.length - 1 ? 0 : '1px',
            background: 'currentColor',
            opacity: v > 0 ? 0.75 : 0.25,
            borderRadius: '1px',
            verticalAlign: 'bottom',
          }}
        />
      ))}
    </>
  );
}
