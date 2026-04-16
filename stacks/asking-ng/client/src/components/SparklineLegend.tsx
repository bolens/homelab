import React from 'react';

type SparklineLegendProps = {
  values: number[];
  bucketLabel: (index: number) => string;
  labels?: {
    min?: string;
    max?: string;
    peak?: string;
  };
};

export default function SparklineLegend({
  values,
  bucketLabel,
  labels = { min: 'Min', max: 'Max', peak: 'Peak' },
}: SparklineLegendProps) {
  const safeValues = values.map((v) => (Number.isFinite(v) && v > 0 ? v : 0));
  const max = safeValues.reduce((m, v) => (v > m ? v : m), 0);
  const min = safeValues.reduce((m, v) => (v < m ? v : m), safeValues[0] ?? 0);
  const peakIndex = safeValues.findIndex((v) => v === max);
  const peakBucket = peakIndex >= 0 ? bucketLabel(peakIndex) : 'n/a';

  return (
    <span>
      {labels.min}: {min} | {labels.max}: {max} | {labels.peak}: {peakBucket} ({max})
    </span>
  );
}
