import React from 'react';
import { cx } from './cx';

type SectionCardProps = React.DetailsHTMLAttributes<HTMLDetailsElement> & {
  summary: React.ReactNode;
  summaryClassName?: string;
};

export default function SectionCard({
  summary,
  summaryClassName,
  className,
  children,
  ...props
}: SectionCardProps) {
  return (
    <details className={cx('ui-section-card', className)} {...props}>
      <summary className={cx('ui-section-card__summary', summaryClassName)}>{summary}</summary>
      {children}
    </details>
  );
}
