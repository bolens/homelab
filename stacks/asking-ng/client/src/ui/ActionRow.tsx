import React from 'react';
import { cx } from './cx';

type ActionRowProps = React.HTMLAttributes<HTMLDivElement> & {
  align?: 'start' | 'center' | 'end';
};

export default function ActionRow({
  align = 'center',
  className,
  children,
  ...props
}: ActionRowProps) {
  return (
    <div
      className={cx(
        'ui-action-row',
        align === 'start' && 'ui-action-row--start',
        align === 'center' && 'ui-action-row--center',
        align === 'end' && 'ui-action-row--end',
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}
