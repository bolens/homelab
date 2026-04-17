import React from 'react';
import { cx } from './cx';

type KpiCardProps = React.HTMLAttributes<HTMLDivElement>;

export default function KpiCard({ className, children, ...props }: KpiCardProps) {
  return (
    <div className={cx('ui-kpi-card', 'asking-admin-page__kpi-card', className)} {...props}>
      {children}
    </div>
  );
}
