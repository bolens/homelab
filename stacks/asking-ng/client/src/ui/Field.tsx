import React from 'react';
import { cx } from './cx';

type FieldProps = React.HTMLAttributes<HTMLDivElement> & {
  label?: string;
  htmlFor?: string;
  hint?: string;
  error?: string;
};

export default function Field({
  label,
  htmlFor,
  hint,
  error,
  className,
  children,
  ...props
}: FieldProps) {
  return (
    <div className={cx('ui-field', className)} {...props}>
      {label ? (
        <label htmlFor={htmlFor} className='ui-field__label'>
          {label}
        </label>
      ) : null}
      {children}
      {hint ? <p className='ui-field__hint'>{hint}</p> : null}
      {error ? (
        <p className='ui-field__error' role='alert'>
          {error}
        </p>
      ) : null}
    </div>
  );
}
