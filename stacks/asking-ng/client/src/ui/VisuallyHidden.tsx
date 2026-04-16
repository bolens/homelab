import React from 'react';
import { cx } from './cx';

export type VisuallyHiddenTag = 'span' | 'p' | 'label' | 'h2' | 'div';

export type VisuallyHiddenProps = {
  as?: VisuallyHiddenTag;
  className?: string;
  children?: React.ReactNode;
  /** Passed through when `as` is `"label"` (React `htmlFor`, not DOM `for`). */
  htmlFor?: string;
} & Omit<React.HTMLAttributes<HTMLElement>, 'className'>;

export default function VisuallyHidden({
  as = 'span',
  className,
  children,
  ...rest
}: VisuallyHiddenProps) {
  return React.createElement(
    as,
    { className: cx('ui-visually-hidden', className), ...rest },
    children,
  );
}
