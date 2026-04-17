import React from 'react';
import { cx } from './cx';

type NoticeTone = 'info' | 'success' | 'error' | 'loading';

type NoticeProps = React.HTMLAttributes<HTMLElement> & {
  as?: 'div' | 'p' | 'span';
  tone?: NoticeTone;
};

const TONE_CLASS: Record<NoticeTone, string> = {
  info: 'ui-notice--info',
  success: 'ui-notice--success',
  error: 'ui-notice--error',
  loading: 'ui-notice--loading',
};

export default function Notice({
  as = 'div',
  tone = 'info',
  className,
  role,
  children,
  ...props
}: NoticeProps) {
  const Comp = as;
  return (
    <Comp
      className={cx('ui-notice', TONE_CLASS[tone], className)}
      role={role ?? (tone === 'error' ? 'alert' : 'status')}
      {...props}
    >
      {children}
    </Comp>
  );
}
