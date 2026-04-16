import React from 'react';
import { cx } from './cx';

type CardProps = React.HTMLAttributes<HTMLElement> & {
  as?: 'section' | 'article' | 'div';
  tone?: 'default' | 'muted' | 'accent';
  padding?: 'none' | 'sm' | 'md' | 'lg';
};

const TONE_CLASS: Record<Exclude<NonNullable<CardProps['tone']>, 'default'>, string> = {
  muted: 'ui-card--muted',
  accent: 'ui-card--accent',
};

const PADDING_CLASS: Record<Exclude<NonNullable<CardProps['padding']>, 'none'>, string> = {
  sm: 'ui-card--sm',
  md: 'ui-card--md',
  lg: 'ui-card--lg',
};

export default function Card({
  as = 'section',
  tone = 'default',
  padding = 'md',
  className,
  children,
  ...props
}: CardProps) {
  const Comp = as;
  return (
    <Comp
      className={cx(
        'ui-card',
        tone !== 'default' && TONE_CLASS[tone],
        padding !== 'none' && PADDING_CLASS[padding],
        className,
      )}
      {...props}
    >
      {children}
    </Comp>
  );
}
