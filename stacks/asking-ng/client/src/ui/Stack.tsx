import React from 'react';
import { cx } from './cx';

type StackProps = React.HTMLAttributes<HTMLDivElement> & {
  gap?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
};

const GAP_CLASS: Record<NonNullable<StackProps['gap']>, string> = {
  xs: 'ui-stack--xs',
  sm: 'ui-stack--sm',
  md: 'ui-stack--md',
  lg: 'ui-stack--lg',
  xl: 'ui-stack--xl',
};

export default function Stack({ gap = 'md', className, children, ...props }: StackProps) {
  return (
    <div className={cx('ui-stack', GAP_CLASS[gap], className)} {...props}>
      {children}
    </div>
  );
}
