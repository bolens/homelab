import React from 'react';
import { cx } from './cx';

type FormSectionProps = React.HTMLAttributes<HTMLElement> & {
  as?: 'section' | 'div';
  title?: React.ReactNode;
  hint?: React.ReactNode;
  titleId?: string;
};

export default function FormSection({
  as = 'section',
  title,
  hint,
  titleId,
  className,
  children,
  ...props
}: FormSectionProps) {
  const Comp = as;
  return (
    <Comp className={cx('ui-form-section', className)} {...props}>
      {title ? (
        <h2 id={titleId} className='ui-form-section__title'>
          {title}
        </h2>
      ) : null}
      {hint ? <p className='ui-form-section__hint'>{hint}</p> : null}
      {children}
    </Comp>
  );
}
