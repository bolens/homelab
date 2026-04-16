import React from 'react';
import { cx } from './cx';

type InlineProps = React.HTMLAttributes<HTMLDivElement> & {
  gap?: 'xs' | 'sm' | 'md' | 'lg';
  wrap?: boolean;
  align?: 'start' | 'center' | 'end';
};

const GAP_CLASS: Record<NonNullable<InlineProps['gap']>, string> = {
  xs: 'ui-inline--xs',
  sm: 'ui-inline--sm',
  md: 'ui-inline--md',
  lg: 'ui-inline--lg',
};

const ALIGN_CLASS: Record<NonNullable<InlineProps['align']>, string> = {
  start: 'ui-inline--start',
  center: 'ui-inline--center',
  end: 'ui-inline--end',
};

export default function Inline({
  gap = 'md',
  wrap = true,
  align = 'center',
  className,
  children,
  ...props
}: InlineProps) {
  return (
    <div
      className={cx(
        'ui-inline',
        GAP_CLASS[gap],
        ALIGN_CLASS[align],
        wrap && 'ui-inline--wrap',
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}
