import React from 'react';
import { cx } from './cx';

type AlertProps = React.HTMLAttributes<HTMLElement> & {
  as?: 'p' | 'div' | 'span' | 'h1' | 'h2' | 'h3';
  tone?: 'danger' | 'warning' | 'info' | 'success';
};

const TONE_CLASS: Record<NonNullable<AlertProps['tone']>, string> = {
  danger: 'ui-alert--danger',
  warning: 'ui-alert--warning',
  info: 'ui-alert--info',
  success: 'ui-alert--success',
};

export default function Alert({
  as = 'p',
  tone = 'danger',
  className,
  role,
  children,
  ...props
}: AlertProps) {
  const Comp = as;
  return (
    <Comp
      role={role ?? (tone === 'danger' ? 'alert' : undefined)}
      className={cx('ui-alert', TONE_CLASS[tone], className)}
      {...props}
    >
      {children}
    </Comp>
  );
}
