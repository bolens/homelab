import React from 'react';
import { cx } from './cx';

type ContainerProps = React.HTMLAttributes<HTMLDivElement> & {
  size?: 'sm' | 'md' | 'lg' | 'xl' | 'full';
};

const SIZE_CLASS: Record<NonNullable<ContainerProps['size']>, string> = {
  sm: 'ui-container--sm',
  md: 'ui-container--md',
  lg: 'ui-container--lg',
  xl: 'ui-container--xl',
  full: 'ui-container--full',
};

export default function Container({ size = 'lg', className, children, ...props }: ContainerProps) {
  return (
    <div className={cx('ui-container', SIZE_CLASS[size], className)} {...props}>
      {children}
    </div>
  );
}
