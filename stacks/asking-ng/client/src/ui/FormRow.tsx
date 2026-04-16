import React from 'react';
import { cx } from './cx';

type FormRowProps = React.HTMLAttributes<HTMLDivElement> & {
  label?: React.ReactNode;
  htmlFor?: string;
  hint?: React.ReactNode;
};

export default function FormRow({
  label,
  htmlFor,
  hint,
  className,
  children,
  ...props
}: FormRowProps) {
  return (
    <div className={cx('ui-form-row', className)} {...props}>
      {label ? (
        <label htmlFor={htmlFor} className='ui-form-row__label'>
          {label}
        </label>
      ) : null}
      {hint ? <p className='ui-form-row__hint'>{hint}</p> : null}
      {children}
    </div>
  );
}
